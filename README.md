# video-render

Public, content-free render runner for CHIJOBHA's videos (Roach Academia, Roki, Bit Badi).
Nothing in this repository is course content: each run downloads the private project from private storage,
renders it, and puts the finished video back in private storage. Access to that storage is granted only to
GitHub Actions runs of this repository's `main` branch (GitHub OIDC), and only to the render folders.
