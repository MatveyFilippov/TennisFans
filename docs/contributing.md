# Contribution and release workflow

1. Start ordinary changes from an updated `dev` branch. Use a single branch such as `codex/feat/tournament-management` and one pull request targeting `dev` for the completed assignment. An authorized hotfix starts from `main`.
2. Use focused Conventional Commits in English, for example `fix(ratings): replay backdated doubles fixtures`. Run the [application checks](development.md) and review the complete diff.
3. The repository owner reviews and merges. The owner later promotes tested changes from `dev` to `main` through a pull request. Synchronize hotfixes back to `dev` after the emergency release through a separate owner action.
4. Update the changelog and follow the [stable release steps](deployment-ubuntu.md). GitHub Pages publishes documentation from `main`.
