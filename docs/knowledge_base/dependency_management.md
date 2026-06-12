# Dependency Management

## Policy

TEAM_ANALYZER uses pinned direct dependencies in `Requirements.txt` and a
fully resolved environment snapshot in `requirements.lock`.

Application changes that add, remove, or upgrade a dependency must update both
files in the same pull request. Unpinned dependencies are prohibited.

## Update Procedure

1. Update the direct version in `Requirements.txt`.
2. Rebuild and review `requirements.lock` in a clean supported Python
   environment.
3. Run the complete test suite.
4. Run `pip-audit -r Requirements.txt`.
5. Submit the change through pull request review.

Dependabot checks Python and GitHub Actions dependencies weekly. Automated
updates remain subject to tests, security scans, and human review.
