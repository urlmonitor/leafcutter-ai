## Post-edit verification (mandatory)

After every Edit/Write batch, run `git diff --stat <touched_paths>` and paste verbatim. For large diffs, also paste the first 5 hunks of `git diff <path>`. In non-git contexts, `Read` the changed line range and paste the extract.

Do not declare success without one of these proofs in the response.

Even if the diff is huge, always paste at least the `--stat` summary and list each touched path explicitly.
