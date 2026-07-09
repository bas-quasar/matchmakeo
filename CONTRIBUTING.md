# Contributing

We welcome contributions and improvements to this package!

Please submit bug reports and feature requests as issues <a href="https://github.com/bas-quasar/matchmakeo/issues/new" target="_blank">on the GitHub repo</a>, <a href="https://github.com/bas-quasar/matchmakeo/discussions" target="_blank">start a discussion</a> or if you don't have a GitHub account, email the maintainers at `dalby [at] bas.ac.uk`.

There are lots of ways to contribute:

## Open new issues and dicussions

### Issues

Best for requesting new features (check out the [existing issues](https://github.com/bas-quasar/matchmakeo/issues) or [roadmap](https://github.com/orgs/bas-quasar/projects/1) first, add to the conversation there) or making bug reports.

[Open a new issue!](https://github.com/bas-quasar/matchmakeo/issues/new)

### Discussions

Best for more general conversations about approaches or how best to achieve something using matchmakeo. If in doubt, start a discussion!

[Start a discussion!](https://github.com/bas-quasar/matchmakeo/discussions)

### If you're not on GitHub

Send us an email at `dalby [at] bas.ac.uk`

## Contributing to code

When making changes to the source code (including to the docs):

1. Fork this repository on GitHub.
1. Clone the package to your computer: `git clone https://github.com/<your-username>/matchmakeo`
1. Inside a virtual environment, install the package as an editable pip install: `pip install -e matchmakeo` (where `matchmakeo` is the relative path to the cloned repository).
1. Also install the development dependency groups: `pip install --group test --group docs --group dev`.
1. Make your changes and run the tests using pytest: `pytest` and/or test the docs build using `properdocs build`.
1. Commit and push your changes to GitHub and open a pull request to the main repo.
