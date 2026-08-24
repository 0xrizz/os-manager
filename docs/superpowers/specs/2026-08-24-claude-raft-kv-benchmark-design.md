# Distributed In-Memory Key-Value Store with Raft Consensus & Chaos Testing (Design Specification)

## 1. Overview & System Goal

The objective is to autonomously build, verify, and benchmark a production-grade, distributed in-memory Key-Value store with **Raft Consensus**, **Disk Write-Ahead Logging (WAL)**, **Snapshot Compaction**, **Jepsen-style Linearizability Verification**, and **Chaos Fault Injection** in pure TypeScript (Node.js v26+, Vitest v3+, ESM).

This benchmark serves as a high-stress test for Claude Code executed through the Headroom (:8787) $\rightarrow$ 9Router (:20128) $\rightarrow$ Gemini 3.7 Flash High pipeline, exercising deep multi-file refactoring, state machine synchronization, and async concurrency patterns.

---

## 2. System Architecture & Component Diagram

```
                              +------------------------------------------+
                              |         RaftKVClient (Cluster)          |
                              |  (Auto Leader Discovery & Exponential    |
                              |   Backoff Linearizable Read/Write)       |
                              +--------------------+---------------------+
                                                   |
                                                   v
+---------------------------------------------------------------------------------------------------+
|                                  VirtualNetwork Transport & Chaos Bus                             |
|        (Simulated Latency, Jitter, Packet Drop, Split-Brain Partitions, Message Reordering)        |
+---------------------+-----------------------------+-----------------------------+-----------------+
                      |                             |                             |
                      v                             v                             v
           +--------------------+        +--------------------+        +--------------------+
           |     RaftNode 1     |        |     RaftNode 2     |        |     RaftNode 3     |
           | (Leader/Candidate/ |        | (Leader/Candidate/ |        | (Leader/Candidate/ |
           |     Follower)      |        |     Follower)      |        |     Follower)      |
           +----------+---------+        +----------+---------+        +----------+---------+
                      |                             |                             |
                      +-----------------------------+-----------------------------+
                                                    |
               +------------------------------------+------------------------------------+
               |                                                                        |
               v                                                                        v
+-----------------------------+                                          +-----------------------------+
|    Write-Ahead Log (WAL)    |                                          |      KV State Machine       |
|  - Disk segment file store  |                                          |  - In-Memory Key-Value Map  |
|  - CRC32 Checksums          |                                          |  - Atomic Compare-And-Swap  |
|  - Fsync durability         |                                          |  - TTL Expiration Min-Heap  |
|  - Snapshot compaction      |                                          |  - Snapshot Serialization   |
+-----------------------------+                                          +-----------------------------+
```

---

## 3. Core Modules & Responsibilities

### Module 1: `src/storage/WriteAheadLog.ts` (Disk WAL & Storage Engine)
* **Storage Format:** Segmented append-only log files with binary/JSON framing, entry index offsets, and CRC32/SHA-256 payload checksums.
* **Fsync Durability:** Configurable synchronous disk flushing (`fsync: true`) and batch buffering.
* **Snapshot & Log Truncation:** Ability to truncate logs prior to `lastIncludedIndex` upon receiving or generating a state snapshot.
* **Recovery:** Crash replay recovering all uncommitted and committed entries from disk into the state machine.

### Module 2: `src/consensus/RaftNode.ts` (Consensus Core & State Machine)
* **States:** `FOLLOWER`, `CANDIDATE`, `LEADER`.
* **RPC Protocols:**
  * `RequestVote(term, candidateId, lastLogIndex, lastLogTerm)` $\rightarrow$ `(term, voteGranted)`.
  * `AppendEntries(term, leaderId, prevLogIndex, prevLogTerm, entries[], leaderCommit)` $\rightarrow$ `(term, success, matchIndex)`.
  * `InstallSnapshot(term, leaderId, lastIncludedIndex, lastIncludedTerm, data)` $\rightarrow$ `(term)`.
* **Timers:** Randomized election timers (150ms–300ms) and periodic heartbeat ticker (50ms).
* **Commit Logic:** Majority quorum calculation ($Q = \lfloor N/2 \rfloor + 1$) for advancing `commitIndex` and applying to state machine.

### Module 3: `src/engine/KVStateMachine.ts` (In-Memory Key-Value Engine)
* **Operations:**
  * `SET(key, value, ttlMs?)`
  * `GET(key)`
  * `DEL(key)`
  * `CAS(key, expectedValue, newValue)` (Compare-And-Swap)
  * `BATCH([commands])` (Atomic multi-key batch execution)
* **TTL Expiration:** Background wheel / Min-Heap for $O(1)$ lazy and active key expiration.
* **Snapshot Engine:** Deterministic JSON/Binary state capture and restore.

### Module 4: `src/network/VirtualNetwork.ts` (Chaos Network Transport)
* **In-Memory Message Bus:** Bidirectional asynchronous message routing between simulated nodes.
* **Fault Injection Features:**
  * `partition(groupA: string[], groupB: string[])` (Simulates split-brain network cut).
  * `heal()` (Restores full cluster connectivity).
  * `setPacketDropRate(rate: number)` (e.g., 0.1 for 10% packet drop).
  * `setLatency(minMs: number, maxMs: number)` (Simulates latency jitter).

### Module 5: `src/client/RaftKVClient.ts` (Cluster Client)
* **Leader Tracking:** Auto-redirects client commands to the current cluster leader.
* **Fault-Tolerant Retries:** Exponential backoff with jitter on network timeouts or leader transitions.
* **Linearizability:** Read lease verification and deduplicated request IDs to ensure exactly-once execution.

### Module 6: `src/verifier/LinearizabilityChecker.ts` (Jepsen-style History Verifier)
* Records an execution history tree: `[Invoke(op), Return(res)]`.
* Verifies that for every concurrent read/write operation, there exists a valid sequential order matching the observed real-time precedence.

### Module 7: `src/bench/BenchmarkRunner.ts` (Throughput & Latency Suite)
* Multi-threaded / async worker client generating 5,000+ operations across 3-node and 5-node clusters.
* Measures ops/sec throughput, p50, p95, and p99 latency percentiles.

---

## 4. Interfaces & Data Contracts

```typescript
export type NodeId = string;

export enum RaftRole {
  FOLLOWER = 'FOLLOWER',
  CANDIDATE = 'CANDIDATE',
  LEADER = 'LEADER',
}

export interface LogEntry<T = unknown> {
  index: number;
  term: number;
  command: T;
  timestamp: number;
}

export interface RequestVoteArgs {
  term: number;
  candidateId: NodeId;
  lastLogIndex: number;
  lastLogTerm: number;
}

export interface RequestVoteReply {
  term: number;
  voteGranted: boolean;
}

export interface AppendEntriesArgs<T = unknown> {
  term: number;
  leaderId: NodeId;
  prevLogIndex: number;
  prevLogTerm: number;
  entries: LogEntry<T>[];
  leaderCommit: number;
}

export interface AppendEntriesReply {
  term: number;
  success: boolean;
  matchIndex: number;
}

export interface InstallSnapshotArgs {
  term: number;
  leaderId: NodeId;
  lastIncludedIndex: number;
  lastIncludedTerm: number;
  data: Uint8Array | string;
}

export interface InstallSnapshotReply {
  term: number;
}

export type KVCommandType = 'SET' | 'GET' | 'DEL' | 'CAS' | 'BATCH';

export interface KVCommand {
  type: KVCommandType;
  key?: string;
  value?: unknown;
  expectedValue?: unknown;
  ttlMs?: number;
  batch?: KVCommand[];
  requestId: string;
}

export interface KVResult<T = unknown> {
  success: boolean;
  value?: T;
  error?: string;
  requestId: string;
}
```

---

## 5. Quality Gates & Verification Standards

1. **Strict TypeScript:** `tsc --noEmit` must pass with 0 errors (`strict: true`, `noImplicitAny: true`).
2. **Vitest Test Suite:** 100% test pass rate across all unit, integration, and chaos test suites.
3. **Zero Placeholders:** No `// TODO`, `// implement later`, or mock bypasses.
4. **Linearizability Guarantee:** Zero stale reads or split-brain inconsistencies under 3-node and 5-node partition tests.
5. **Benchmark Execution:** Benchmark suite must execute and report measurable throughput (ops/sec).
