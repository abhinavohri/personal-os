# Daily adaptive plan

Prepare the upcoming waking day's plan for the current calendar date in
Asia/Kolkata. This is a fresh scheduled session.

1. Read `agent_brief` and `current_week` with
   `personal_os_read_context`.
2. Run `personal_os_execution_review` with a 14-day window.
3. Save the evidence snapshot with
   `personal_os_save_execution_review_draft` using the same window.
4. Use observed execution, overdue work, rollovers, GitHub evidence, hard
   deadlines, and approved strategic context. Do not ask for an estimate of
   available weekly hours.

Return a concise draft containing:

- the date;
- no more than two core actions;
- no more than one optional action;
- carryovers or blockers;
- why the load or order changed; and
- anything requiring user approval.

Prefer shrinking or reordering existing work over adding more. Do not create or
edit Todoist tasks, change the roadmap, send messages, apply to jobs, or change
GitHub. End by stating that the plan is a draft awaiting review.
