# Database Internals curriculum

The course comprises 10 units, 48 core lessons, 10 checkpoints, and 9 interactive labs. Unit 1 is fully authored in the initial build; subsequent units are represented in the course map and are the content production sequence.

1. **Bytes to rows** — latency hierarchy; blocks and pages; row layout; slotted pages; heap files; lab: Page Surgeon.
2. **Indexes that scale** — sorted access; B+ tree anatomy; search; splits/merges; clustered vs secondary indexes; LSM trees; Bloom filters; lab: Tree Operator.
3. **Memory is the database** — locality; buffer pool; pin/dirty state; CLOCK/LRU; prefetch; double buffering; lab: Eviction Arena.
4. **Executing a query** — iterator/vectorized models; scans; external sort; hash join; merge join; nested loops; aggregation; lab: Operator Factory.
5. **Planning a query** — statistics; cardinality estimation; selectivity; cost models; join ordering; plan instability; adaptive execution; lab: Plan Detective.
6. **Transactions and MVCC** — ACID precisely; schedules; snapshots; tuple versions; isolation levels; anomalies; vacuum; lab: Time-Travel Table.
7. **Concurrency control** — latches vs locks; 2PL; intention locks; deadlocks; optimistic control; SSI; hot spots; lab: Deadlock Lab.
8. **Durability and recovery** — WAL; physiological logging; checkpoints; ARIES analysis/redo/undo; torn pages; group commit; lab: Crash Recovery Console.
9. **Replication and partitioning** — physical/logical replication; sync/async; lag; failover; split brain; sharding; rebalancing; consistent hashing; lab: Replica Control Room.
10. **Distributed databases** — time and ordering; consensus; Raft; distributed transactions; 2PC; serializability; Spanner-style clocks; CAP/PACELC; lab: Consensus Timeline.

Each checkpoint mixes recall, transfer, trace prediction, and diagnosis. Completion requires 80%; mastery requires a later review at 90%.
