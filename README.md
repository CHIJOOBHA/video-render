# video-render

Public, content-free render runner for CHIJOBHA's videos (Roach Academia, Roki, Bit Badi).
Nothing in this repository is course content: each run downloads the private project from private storage,
renders it, and puts the finished video back in private storage. Access to that storage is granted only to
GitHub Actions runs of this repository's `main` branch (GitHub OIDC), and only to the render folders.

## Telugu voice on GPUs (5 Nov 2026)
`gpu/voice.py` tries each GPU platform in the order in `queue/gpu-order` and uses the first that voices every sentence;
if none does, the 16 free GitHub CPU machines take over as before. A platform is tried only when its secrets are saved
(repo Settings → Secrets and variables → Actions):

| Platform | Secrets | Cost |
|---|---|---|
| Modal | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | free $30 of GPU time a month; one video split over up to 8 GPUs at once |
| Kaggle | `KAGGLE_USERNAME`, `KAGGLE_KEY` | free, about 30 GPU hours a week; one GPU |
| RunPod | `RUNPOD_API_KEY` | paid per minute; machine switched off as soon as the voice is done |
| Vast.ai | `VAST_API_KEY` | paid per minute, only offers under $0.45/h; switched off as soon as done |

Rented machines (RunPod, Vast.ai) never get a key: only two 2-hour links, one to download the job, one to upload the wavs.
With Modal set up, the Telugu queue runs up to 3 Telugu videos at once (`queue/te-max` overrides the number).
