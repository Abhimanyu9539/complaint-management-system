"""Evaluation-dataset tooling.

Deliberately thin. deepeval's `deepeval generate` CLI does the actual golden
synthesis (see `tests/evals/README.md`); this package only supplies the two
things the CLI cannot do for itself — turning `cases.json` into the contexts
file `--method contexts` expects, and joining the two generated files back into
one dataset with ground-truth metadata attached.

Nothing here runs at eval time. The dataset is a build artifact that is
generated, reviewed, and committed; the Step 6 LangSmith runner consumes it.
"""
