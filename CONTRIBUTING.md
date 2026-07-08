# Contributing

We welcome contributions and improvements to this package!

Please submit bug reports and feature requests as issues <a href="https://github.com/bas-quasar/matchmakeo/issues/new" target="_blank">on the GitHub repo</a>, <a href="https://github.com/bas-quasar/matchmakeo/discussions" target="_blank">start a discussion</a> or if you don't have a GitHub account, email the maintainers at `dalby [at] bas.ac.uk`.

## Contributing Guide

When making changes to the source code (including to the docs):

1. Fork this repository on GitHub.
1. Clone the package to your computer: `git clone https://github.com/<your-username>/matchmakeo`
1. Inside a virtual environment, install the package as an editable pip install: `pip install -e matchmakeo` (where `matchmakeo` is the relative path to the cloned repository).
1. Also install the development dependency groups: `pip install --group test --group docs --group dev`.
1. Make your changes and run the tests using pytest: `pytest` and/or test the docs build using `properdocs build`.
1. Commit and push your changes to GitHub and open a pull request to the main repo.
