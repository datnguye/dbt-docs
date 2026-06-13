---
description: Review the current dbdocs change for consistency, Python pluggability, design-pattern alignment, the 3-tier bundle-JS contract, complexity/scale, and the generated-SPA UX & accessibility.
---

Use the **dbdocs-code-review** skill to review dbdocs changes against this
codebase's documented patterns.

Target (in order of precedence):
1. If `$ARGUMENTS` names a PR number, branch, or path, review that.
2. Otherwise review the working-tree diff (`git diff` + untracked new files).

Follow the skill's six dimensions — **Consistency**, **Pluggable (Python
modules)**, **Align with design patterns**, **3-tier bundle JS**, **Complexity /
scale**, **UX & accessibility** — run the gates (report, don't fix), and emit the
severity-graded findings report in the skill's output format.

Do not modify any files during the review. End by offering to apply the
behavior-neutral findings (all / high-severity subset / none).
