# TennisFans

TennisFans tracks recreational singles and doubles tennis. Public pages show matches, tournament schedules and standings, photos, and one Elo rating per player. Registered players submit their own results, apply to tournaments, and dispute opposing submissions.

The FastAPI backend and React frontend run as separate processes. The API connects to an externally managed PostgreSQL 16+ database and stores image files in a persistent local directory. The dynamic site runs independently of the documentation published to GitHub Pages.

- [Local development and test commands](docs/development.md)
- [Ubuntu 24.04 installation and GitHub owner setup](docs/deployment-ubuntu.md)
- [Player, organizer, and administrator guide](docs/user-guide.md)
- [API, scoring, and architecture](docs/architecture.md)
- [Backup, restore, and host migration](docs/backup-and-restore.md)

## Runtime

- Python 3.12 and PostgreSQL 16+ for the API.
- Node.js 24 for frontend development, build, and the reference static server. An existing static SPA server can serve the built files.
- [MIT License](LICENSE).
