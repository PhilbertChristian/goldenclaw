# Max the Golden Token Retrieval 🐶

> Wake Max. He fetches your tokens.

![Max wakes up and fetches your token quota](demo.gif)

You pay for an AI subscription. You have no idea how much of it you actually
use. **Max knows.** He lives in your terminal, reads your *real* Claude
quota, and tells you what's about to expire before it does. He never
guesses: every number he shows comes from your provider or your own logs.

## Get Max — one line

```bash
curl -fsSL https://raw.githubusercontent.com/PhilbertChristian/max/main/install.sh | sh
```

That's the whole onboarding: Max installs, wakes up, introduces himself,
checks his own setup, and shows your first live read. (Prefer doing it
yourself? `pipx install git+https://github.com/PhilbertChristian/max` then
`max init`.)

## The whole thing is one word

```
$ max
        ( Max wakes up )

  Max is listening.  ask about your tokens · `exit` to leave

  you › tokens
        ( sniffing for tokens… )
  Max › CLAUDE · MAX plan
        session (5h)       ▐████████▌ 93% left · resets in 4h
        week · all models  ▐████░░░░▌ 39% left · ≈ $182 left at your mix

  you › monthly
        ( where did I bury my claws again? )
  Max › this month, by model:
          claude-fable-5    231.4M   $358.74
          claude-opus-5     134.8M   $98.16
          total $530.28 · 451.4M tokens
```

Quota answers are instant and free — they're code, not model calls. Anything
else you type is a real conversation with him.

And in your menu bar, `🐶 41%` all day:

```bash
brew install --cask swiftbar && max menubar --install
```

## House rules

- **He never invents a number.** Live quota comes from Anthropic's own usage
  endpoint, via the credential your `claude` CLI already stores. History
  comes from your local logs. What he can't verify, he won't show.
- **Checking your tokens never spends your tokens.** Quota displays are
  code, not model calls. Only talking to him (`max`) uses your plan.
- **One network call, to your own provider, about your own account.**
  Nothing else leaves your machine. `--offline` kills even that.
- **Tiny footprint, all opt-in.** A pipx venv, `~/.config/max/`, and — only
  if you say yes — a shell-rc block and a 4-line menu bar plugin. Undo:
  `pipx uninstall max-token-retrieval`, delete the folder, done.

Deep dives: [methodology](docs/methodology.md) ·
[architecture](docs/architecture.md) · experimental overnight runner:
`max goodnight --help`

## Credits

Max was drawn by **Hayley Jane Wakenshaw** (with the classic sleeping
figure), from [Christopher Johnson's ASCII Art Collection](https://asciiart.website).
Spiritual ancestors: [NanoClaw](https://github.com/qwibitai/nanoclaw),
[baby-menu](https://github.com/kunchenguid/baby-menu). Claude-only today,
and honest about it.

MIT — see [LICENSE](LICENSE).
