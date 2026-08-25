# PageCraft product requirements

## Product promise

PageCraft makes advanced computer-science systems knowledge learnable through short explanations, manipulable models, prediction, and immediate feedback. Its first complete course is Database Internals.

## Audience

Software engineers and CS students moving from basic SQL knowledge toward intermediate and expert systems understanding. Learners should know basic programming and SQL; unfamiliar operating-system concepts are introduced in context.

## Core loop

1. Continue from the next recommended lesson.
2. Read one compact mental model.
3. Predict or manipulate a database mechanism.
4. Receive immediate, explanatory feedback.
5. Earn XP and mastery; mistakes enter review.
6. Complete a checkpoint to unlock the next unit.

## Required product surfaces

- Home: daily goal, streak, XP, continue action, recent mastery, review queue.
- Learn: scrollable course path with units, prerequisites, lesson state, checkpoints.
- Lesson player: progress, hearts, keyboard controls, explanations, exercises, summary.
- Labs: page inspector, B+ tree operations, buffer-pool eviction, plan builder, MVCC timeline, lock graph, WAL recovery, replication-lag model, consensus timeline.
- Review: mistakes and weak skills prioritized using confidence and recency.
- Progress: unit mastery, completed lessons, accuracy, XP, achievements.
- Reference: searchable glossary of database-internals terms.

## Learning mechanics

- Five hearts per lesson; an incorrect graded attempt costs one.
- XP: 10 per correct first attempt, 6 after a retry, lesson and perfect bonuses.
- Streak: increments on the first completed lesson of a learner-local calendar day.
- Mastery: unseen, familiar, practiced, mastered. Confidence decays into the review queue.
- Lesson states: locked, available, in progress, completed, mastered.
- Checkpoints require 80% accuracy and can be retried without losing course progress.
- Exercise types: single choice, multiple choice, ordering, matching, numeric prediction, code/SQL, hotspot/model manipulation, and simulation.

## Content quality bar

Every lesson must include a motivating failure mode, a precise mental model, at least one visual or simulation, prediction before explanation where suitable, graded practice with meaningful distractors, and a concise takeaway. No lesson may ship as title-only placeholder content.

## Non-goals for this release

Authentication, payments, public profiles, leagues, social features, a visual course-authoring CMS, native mobile apps, and high-scale deployment infrastructure.

## Acceptance criteria

- A new learner can start without setup and resume after restarting the browser or containers.
- All units and lesson descriptions are visible; Unit 1 is fully playable end-to-end.
- Answers are validated by the server and progress is persisted in PostgreSQL.
- The interface works at 360px width, supports keyboard operation, honors reduced motion, and exposes accessible names and focus states.
- Empty, loading, success, locked, error, retry, and completion states are designed.
