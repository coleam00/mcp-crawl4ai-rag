Parallel PRP creation

YOU MUST READ THESE FILES AND FOLLOW THE INSTRUCTIONS IN THEM.
Start by reading the PRPs/README.md to understand what a PRP is and how it works.
Then read PRPs/templates/prp_base.md to understand the structure of a PRP.

Think hard about the concept of a PRP and how it works.

Help the user create a several Product Requirement Prompt (PRP) in parallel using subagents.

Feature idea: $ARGUMENTS

Come up with a good PRP_NAME for the feature based on the feature idea.

Instructions
We're going to create 3 subagents to create 3 versions of the same PRP in parallel.

This enables us to concurrently spec out the same feature in parallel so we can test and validate each subagent's implementation plan in isolation then pick the best implementation plan.

The first agent will create PRP_NAME-1.md The second agent will create PRP_NAME-2.md and the last agent will create PRP_NAME-3.md


When the subagent completes it's work, have the subagent to report their final changes made in a comprehensive RESULTS_PRP_NAME-<number>.md file at the root of the repository.

Make sure agents don't change any code or run any scripts that would start the server or client - focus resarch and PRP creation only.