import type {
  CurriculumTopic,
  LearningProject,
  ResourceItem,
  SimulatedPlan,
} from './types'

export const SAMPLE_TOPICS: CurriculumTopic[] = [
  {
    id: 'variables',
    title: 'Variables and data types',
    objective: 'Understand names, integer/float/string types, and value reassignment.',
    difficulty: 1,
    learn_minutes: 15,
    practice_minutes: 15,
    prerequisites: [],
  },
  {
    id: 'conditions',
    title: 'Conditions',
    objective: 'Trace if, elif, and else branches with comparison and Boolean operators.',
    difficulty: 2,
    learn_minutes: 15,
    practice_minutes: 15,
    prerequisites: ['variables'],
  },
  {
    id: 'loops',
    title: 'Loops',
    objective: 'Trace for and while iterations, range bounds, and accumulator updates.',
    difficulty: 2,
    learn_minutes: 20,
    practice_minutes: 20,
    prerequisites: ['conditions'],
  },
  {
    id: 'functions',
    title: 'Functions',
    objective: 'Define reusable functions, bind arguments to parameters, and return calculated values.',
    difficulty: 3,
    learn_minutes: 20,
    practice_minutes: 25,
    prerequisites: ['loops'],
  },
]

export const BUNDLED_RESOURCES: ResourceItem[] = [
  {
    id: 'res-python-basics',
    title: 'Python Basics.pdf',
    filename: 'Python Basics.pdf',
    kind: 'bundled',
    mimeType: 'application/pdf',
    byteSize: 142800,
    topicIds: ['variables'],
    sourceLabel: 'Sample resource',
    snippet:
      'Variable assignment binds a descriptive name to an object in memory. Numeric operations (+, -, *, /) follow standard arithmetic precedence.',
    previewType: 'bundled-text',
    fullText: `Python Basics Reference Guide

1. Variable Assignment and State
Variables store references to values. Assignment using the equals sign binds an identifier to an evaluated value:
    counter = 0
    total_score = 94.5
    user_name = "Alex"

Reassigning a variable updates what the identifier points to without altering other names:
    score = 10
    total = score
    score = 20  # total remains 10

2. Core Data Types
- Integers (int): Whole numbers like 42 or -7.
- Floats (float): Decimal approximations like 3.14159.
- Strings (str): Ordered character sequences enclosed in quotes.
- Booleans (bool): Either True or False.

3. Type Casting and Best Practices
Explicitly convert types when combining inputs:
    age_str = "19"
    age_int = int(age_str)
Use descriptive snake_case names for all local variables.`,
    sections: [
      {
        title: 'Variable Assignment and State',
        pageNumber: 1,
        content:
          'Variables store references to values. Assignment binds an identifier to an evaluated value. Reassigning updates what the identifier points to.',
      },
      {
        title: 'Core Data Types',
        pageNumber: 2,
        content:
          'Integers, Floats, Strings, and Booleans form the primary primitive building blocks of Python programs.',
      },
      {
        title: 'Type Casting and Best Practices',
        pageNumber: 3,
        content:
          'Convert types explicitly when processing raw input. Follow PEP 8 snake_case naming conventions.',
      },
    ],
    addedAt: '2026-10-28T09:00:00Z',
  },
  {
    id: 'res-control-flow',
    title: 'Control Flow Notes.pdf',
    filename: 'Control Flow Notes.pdf',
    kind: 'bundled',
    mimeType: 'application/pdf',
    byteSize: 198400,
    topicIds: ['conditions', 'loops'],
    sourceLabel: 'Sample resource',
    snippet:
      'Conditions evaluate expressions to Boolean truth values. Loops repeatedly execute a block of statements while a condition holds or over an iterable.',
    previewType: 'bundled-text',
    fullText: `Control Flow and Iteration Notes

1. Branching with if, elif, and else
Branches let programs make decisions:
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    else:
        grade = "C"

2. Definite Iteration with for Loops
for loops visit items of an iterable sequence in order:
    total = 0
    for number in range(1, 6):
        total += number  # total updates to 1, 3, 6, 10, 15

3. Range Function Endpoints
range(start, stop[, step]) produces integers from start up to, but excluding, stop:
    range(0, 5) yields 0, 1, 2, 3, 4 (5 elements total)

4. While Loops and Termination Invariants
while loops repeat while an expression remains true. Ensure the loop condition variable advances toward termination:
    step = 0
    while step < 3:
        step += 1`,
    sections: [
      {
        title: 'Branching with if, elif, and else',
        pageNumber: 1,
        content:
          'Conditional statements evaluate expressions to determine which branch of code executes.',
      },
      {
        title: 'Definite Iteration with for Loops',
        pageNumber: 2,
        content:
          'The for loop iterates over sequences such as range(), strings, and lists in deterministic order.',
      },
      {
        title: 'Range Function Endpoints and Accumulators',
        pageNumber: 3,
        content:
          'The range(start, stop) function excludes the stop endpoint. Accumulators store aggregate state across loop iterations.',
      },
    ],
    addedAt: '2026-10-28T09:15:00Z',
  },
  {
    id: 'res-functions-practice',
    title: 'Functions and Practice.md',
    filename: 'Functions and Practice.md',
    kind: 'bundled',
    mimeType: 'text/markdown',
    byteSize: 84300,
    topicIds: ['functions'],
    sourceLabel: 'Sample resource',
    snippet:
      'Functions encapsulate code into reusable units with parameter inputs and returned results. Distinguish printing from returning values.',
    previewType: 'bundled-text',
    fullText: `# Functions and Structured Practice

## 1. Function Syntax and Scope
Define a function with \`def\`, specify parameters, and provide an indented body:
\`\`\`python
def calculate_area(width: float, height: float) -> float:
    return width * height
\`\`\`
Parameters are local to the function execution frame and do not collide with global variables.

## 2. Returning Values vs Printing
- \`print()\` outputs text to the console for human viewing; it returns \`None\`.
- \`return\` sends a computed value back to the caller for assignment or expression evaluation:
\`\`\`python
# Correct pattern:
result = calculate_area(4, 5)
double_area = result * 2
\`\`\`

## 3. Worked Practice Exercise: Accumulator Function
\`\`\`python
def sum_evens(limit: int) -> int:
    total = 0
    for n in range(2, limit + 1, 2):
        total += n
    return total

assert sum_evens(6) == 12  # 2 + 4 + 6
\`\`\``,
    sections: [
      {
        title: 'Function Syntax and Scope',
        pageNumber: 1,
        content:
          'Functions isolate local variables within their execution frame and accept parameters to operate on.',
      },
      {
        title: 'Return Values vs Console Printing',
        pageNumber: 2,
        content:
          'Returning produces values usable by subsequent expressions. Printing is side-effect output only.',
      },
      {
        title: 'Accumulator Functions Worked Example',
        pageNumber: 3,
        content:
          'Writing clean helper functions that compute totals using accumulator loops with unit assertions.',
      },
    ],
    addedAt: '2026-10-28T09:30:00Z',
  },
]

export const SAMPLE_PROJECT: LearningProject = {
  id: 'proj-python-fundamentals-01',
  title: 'Python Fundamentals',
  description: 'Master core foundations from variables to functions before the upcoming assessment.',
  curriculumId: 'python-foundations-v1',
  createdAt: '2026-10-28T10:00:00Z',
  updatedAt: '2026-10-28T10:30:00Z',
  resourceIds: ['res-python-basics', 'res-control-flow', 'res-functions-practice'],
  studyScope: {
    selectedTopicIds: ['variables', 'conditions', 'loops', 'functions'],
    selectedResourceIds: ['res-python-basics', 'res-control-flow', 'res-functions-practice'],
    freeTextRequest: 'Need to feel confident tracing loop accumulators and writing clean functions.',
    confirmedAt: '2026-10-28T10:35:00Z',
  },
}

export const INITIAL_PLAN_V1: SimulatedPlan = {
  planId: 'plan-py-fund-v1',
  projectId: 'proj-python-fundamentals-01',
  version: 1,
  status: 'active',
  totalMinutes: 140,
  feasibility: 'full',
  createdAt: '2026-10-28T10:40:00Z',
  entries: [
    {
      entryId: 'entry-01',
      topicId: 'variables',
      topicTitle: 'Variables and data types',
      activityKind: 'learn',
      activityTitle: 'Read variables examples',
      durationMinutes: 15,
      resourceIds: ['res-python-basics'],
      resourceName: 'Python Basics.pdf',
      scheduledDay: 'Day 1',
      sequence: 1,
      completed: true,
      summary: 'Read core data types and practice variable reassignments.',
      steps: [
        'Review identifier naming rules and PEP 8 snake_case conventions.',
        'Observe memory reference assignment and value updates with the equals sign.',
        'Trace type casting examples using int(), float(), and str().',
      ],
      expectedOutcome: 'Ability to name variables cleanly and cast types without syntax errors.',
    },
    {
      entryId: 'entry-02',
      topicId: 'variables',
      topicTitle: 'Variables and data types',
      activityKind: 'practice',
      activityTitle: 'Evaluate expressions drill',
      durationMinutes: 15,
      resourceIds: ['res-python-basics'],
      resourceName: 'Python Basics.pdf',
      scheduledDay: 'Day 1',
      sequence: 2,
      completed: true,
      summary: 'Solve 4 type conversion and expression evaluation tracing items.',
      steps: [
        'Complete 4 variable reassignment trace items step-by-step.',
        'Evaluate operator precedence across arithmetic expressions (*, /, +, -).',
        'Verify string concatenation versus numeric arithmetic behavior.',
      ],
      expectedOutcome: 'Accurately predict expression output and state mutations without side effects.',
    },
    {
      entryId: 'entry-03',
      topicId: 'conditions',
      topicTitle: 'Conditions',
      activityKind: 'learn',
      activityTitle: 'Trace conditional branches',
      durationMinutes: 15,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 2',
      sequence: 1,
      completed: false,
      summary: 'Inspect if-elif-else branch conditions and truth value tables.',
      steps: [
        'Analyze if-elif-else branch conditions and compound comparisons (and, or, not).',
        'Map out mutually exclusive decision branches for grade assignments.',
        'Verify that edge condition boundaries (e.g. >= 80 vs > 80) match specifications.',
      ],
      expectedOutcome: 'Understand boolean expression branch resolution without missing fallback conditions.',
    },
    {
      entryId: 'entry-04',
      topicId: 'loops',
      topicTitle: 'Loops',
      activityKind: 'learn',
      activityTitle: 'Trace loop range bounds',
      durationMinutes: 20,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 2',
      sequence: 2,
      completed: false,
      summary: 'Trace for loop range bounds and step through accumulator updates.',
      steps: [
        'Examine range(start, stop, step) non-inclusive stop endpoints.',
        'Trace total accumulator updates across iterations 1 to 5.',
        'Verify while loop loop-continuation condition and termination guarantee.',
      ],
      expectedOutcome: 'Prevent off-by-one errors and loop stalls when constructing iteration bounds.',
    },
    {
      entryId: 'entry-05',
      topicId: 'loops',
      topicTitle: 'Loops',
      activityKind: 'practice',
      activityTitle: 'Practice loop exercises',
      durationMinutes: 20,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 3',
      sequence: 1,
      completed: false,
      summary: 'Complete accumulator iteration drills and verify off-by-one bounds.',
      steps: [
        'Solve 3 practice exercises accumulating sums and count tallies.',
        'Trace loop variables step-by-step on scratchpad to confirm final value.',
        'Implement an early termination condition using a boolean flag.',
      ],
      expectedOutcome: 'Confidence running accumulator updates in both for and while constructs.',
    },
    {
      entryId: 'entry-06',
      topicId: 'functions',
      topicTitle: 'Functions',
      activityKind: 'learn',
      activityTitle: 'Study function return values',
      durationMinutes: 20,
      resourceIds: ['res-functions-practice'],
      resourceName: 'Functions and Practice.md',
      scheduledDay: 'Day 3',
      sequence: 2,
      completed: false,
      summary: 'Study parameter passing and returning values vs console printing.',
      steps: [
        'Review def syntax, parameter lists, and type annotations.',
        'Differentiate return values from console print() calls and None returns.',
        'Trace local variable scope lifetime within the function frame.',
      ],
      expectedOutcome: 'Construct pure helper functions that produce reusable return values.',
    },
    {
      entryId: 'entry-07',
      topicId: 'functions',
      topicTitle: 'Functions',
      activityKind: 'check',
      activityTitle: 'Write a small accumulator function',
      durationMinutes: 35,
      resourceIds: ['res-functions-practice'],
      resourceName: 'Functions and Practice.md',
      scheduledDay: 'Day 4',
      sequence: 1,
      completed: false,
      summary: 'Build a working accumulator function and verify with assertions.',
      steps: [
        'Define sum_evens(limit: int) -> int with input validation.',
        'Implement the accumulator loop using range(2, limit + 1, 2).',
        'Verify returned output against assert sum_evens(6) == 12.',
      ],
      expectedOutcome: 'Pass unit assertions with a clean, documented accumulator function.',
    },
  ],
}

export const SAMPLE_REPLAN_REQUEST_LOOPS = {
  reason: 'Spend more time on loops and spread the remaining work over more days.',
  focusTopicIds: ['loops'],
  deadlineChanged: true,
  newTargetDate: '2026-11-04',
  dailyStudyMinutes: 35,
  preservePreferences: 'Keep completed Day 1 sessions and preserve original resource selections.',
}

export const SAMPLE_PLAN_V2: SimulatedPlan = {
  planId: 'plan-py-fund-v2',
  projectId: 'proj-python-fundamentals-01',
  version: 2,
  status: 'active',
  totalMinutes: 155,
  feasibility: 'full',
  createdAt: '2026-10-28T11:00:00Z',
  replanReason:
    'Spend more time on loops and spread the remaining work over more days (capped under 35 min/day).',
  changeSummary: {
    headline: 'Spread remaining work across 5 days with targeted loop reinforcement',
    changes: [
      'Added 1 targeted 15-minute reinforcement drill on Day 3: "Reinforce loop accumulators drill".',
      'Redistributed sessions across 5 days so daily study time stays under 35 minutes.',
      'Moved Functions check to Day 5 for dedicated practice.',
    ],
    preservedItems: [
      'Preserved completed Day 1 sessions (Read variables examples, Evaluate expressions drill).',
      'Preserved all confirmed topic and resource references without orphaned IDs.',
    ],
    durationDeltaMinutes: 15,
  },
  entries: [
    {
      entryId: 'entry-01',
      topicId: 'variables',
      topicTitle: 'Variables and data types',
      activityKind: 'learn',
      activityTitle: 'Read variables examples',
      durationMinutes: 15,
      resourceIds: ['res-python-basics'],
      resourceName: 'Python Basics.pdf',
      scheduledDay: 'Day 1',
      sequence: 1,
      completed: true,
      summary: 'Read core data types and practice variable reassignments.',
      steps: [
        'Review identifier naming rules and PEP 8 snake_case conventions.',
        'Observe memory reference assignment and value updates with the equals sign.',
        'Trace type casting examples using int(), float(), and str().',
      ],
      expectedOutcome: 'Ability to name variables cleanly and cast types without syntax errors.',
    },
    {
      entryId: 'entry-02',
      topicId: 'variables',
      topicTitle: 'Variables and data types',
      activityKind: 'practice',
      activityTitle: 'Evaluate expressions drill',
      durationMinutes: 15,
      resourceIds: ['res-python-basics'],
      resourceName: 'Python Basics.pdf',
      scheduledDay: 'Day 1',
      sequence: 2,
      completed: true,
      summary: 'Solve 4 type conversion and expression evaluation tracing items.',
      steps: [
        'Complete 4 variable reassignment trace items step-by-step.',
        'Evaluate operator precedence across arithmetic expressions (*, /, +, -).',
        'Verify string concatenation versus numeric arithmetic behavior.',
      ],
      expectedOutcome: 'Accurately predict expression output and state mutations without side effects.',
    },
    {
      entryId: 'entry-03',
      topicId: 'conditions',
      topicTitle: 'Conditions',
      activityKind: 'learn',
      activityTitle: 'Trace conditional branches',
      durationMinutes: 15,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 2',
      sequence: 1,
      completed: false,
      summary: 'Inspect if-elif-else branch conditions and truth value tables.',
      steps: [
        'Analyze if-elif-else branch conditions and compound comparisons (and, or, not).',
        'Map out mutually exclusive decision branches for grade assignments.',
        'Verify that edge condition boundaries match specifications.',
      ],
      expectedOutcome: 'Understand boolean expression branch resolution without missing fallback conditions.',
    },
    {
      entryId: 'entry-04',
      topicId: 'loops',
      topicTitle: 'Loops',
      activityKind: 'learn',
      activityTitle: 'Trace loop range bounds',
      durationMinutes: 20,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 2',
      sequence: 2,
      completed: false,
      summary: 'Trace for loop range bounds and step through accumulator updates.',
      steps: [
        'Examine range(start, stop, step) non-inclusive stop endpoints.',
        'Trace total accumulator updates across iterations 1 to 5.',
        'Verify while loop loop-continuation condition and termination guarantee.',
      ],
      expectedOutcome: 'Prevent off-by-one errors and loop stalls when constructing iteration bounds.',
    },
    {
      entryId: 'entry-05',
      topicId: 'loops',
      topicTitle: 'Loops',
      activityKind: 'practice',
      activityTitle: 'Practice loop exercises',
      durationMinutes: 20,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 3',
      sequence: 1,
      completed: false,
      summary: 'Complete accumulator iteration drills and verify off-by-one bounds.',
      steps: [
        'Solve 3 practice exercises accumulating sums and count tallies.',
        'Trace loop variables step-by-step on scratchpad to confirm final value.',
        'Implement an early termination condition using a boolean flag.',
      ],
      expectedOutcome: 'Confidence running accumulator updates in both for and while constructs.',
    },
    {
      entryId: 'entry-08',
      topicId: 'loops',
      topicTitle: 'Loops',
      activityKind: 'practice',
      activityTitle: 'Reinforce loop accumulators drill',
      durationMinutes: 15,
      resourceIds: ['res-control-flow'],
      resourceName: 'Control Flow Notes.pdf',
      scheduledDay: 'Day 3',
      sequence: 2,
      completed: false,
      summary: 'Targeted reinforcement check tracing while-loop invariants and bounds.',
      steps: [
        'Trace nested loop counters on scratchpad with intermediate tallies.',
        'Evaluate while-loop accumulator termination conditions under edge bounds.',
        'Verify loop invariants without index drift or off-by-one mistakes.',
      ],
      expectedOutcome: 'Fluid mastery of loop accumulator bounds before writing functions.',
    },
    {
      entryId: 'entry-06',
      topicId: 'functions',
      topicTitle: 'Functions',
      activityKind: 'learn',
      activityTitle: 'Study function return values',
      durationMinutes: 20,
      resourceIds: ['res-functions-practice'],
      resourceName: 'Functions and Practice.md',
      scheduledDay: 'Day 4',
      sequence: 1,
      completed: false,
      summary: 'Study parameter passing and returning values vs console printing.',
      steps: [
        'Review def syntax, parameter lists, and type annotations.',
        'Differentiate return values from console print() calls and None returns.',
        'Trace local variable scope lifetime within the function frame.',
      ],
      expectedOutcome: 'Construct pure helper functions that produce reusable return values.',
    },
    {
      entryId: 'entry-07',
      topicId: 'functions',
      topicTitle: 'Functions',
      activityKind: 'check',
      activityTitle: 'Write a small accumulator function',
      durationMinutes: 35,
      resourceIds: ['res-functions-practice'],
      resourceName: 'Functions and Practice.md',
      scheduledDay: 'Day 5',
      sequence: 1,
      completed: false,
      summary: 'Build a working accumulator function and verify with assertions.',
      steps: [
        'Define sum_evens(limit: int) -> int with input validation.',
        'Implement the accumulator loop using range(2, limit + 1, 2).',
        'Verify returned output against assert sum_evens(6) == 12.',
      ],
      expectedOutcome: 'Pass unit assertions with a clean, documented accumulator function.',
    },
  ],
}

