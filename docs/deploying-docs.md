# Deploying the docs to Read the Docs

This project's docs (this MkDocs site) are ready to host on
[Read the Docs](https://readthedocs.org) — `.readthedocs.yaml` and
`mkdocs.yml` are already committed and configured, so importing the
project is a few clicks with no further setup. This page walks through
that one-time import.

## Prerequisites (already done)

- The GitHub repo ([wsnoble/google-photo-book](https://github.com/wsnoble/google-photo-book))
  is public — Read the Docs' free tier requires a public repo (or a paid
  plan for private ones).
- `.readthedocs.yaml` at the repo root tells Read the Docs how to build:
  Ubuntu 24.04, Python 3.13, MkDocs with `mkdocs.yml` as the config file,
  and doc dependencies from `docs/requirements.txt`.
- `mkdocs.yml` defines the site itself (nav, theme, pages).

None of this needs to change to deploy — it's already correct.

## 1. Sign up / log in

Go to [readthedocs.org](https://readthedocs.org) and sign in with your
GitHub account (**Sign up with GitHub**). This is what lets Read the Docs
list your repos and set up the webhook in the next step.

## 2. Import the project

1. From your Read the Docs dashboard, click **Add project**.
2. Choose **Import a Repository**, then select `wsnoble/google-photo-book`
   from the list of your GitHub repos. If it doesn't show up, click
   **refresh your accounts** — Read the Docs caches your repo list.
3. Confirm the project name/slug it proposes (defaults to `google-photo-book`)
   and click **Next**.

This step also installs a webhook on the GitHub repo, so future pushes to
`main` trigger an automatic rebuild — nothing further to configure for
that.

## 3. First build

Read the Docs kicks off a build automatically right after import. Watch
it from the project's **Builds** tab. It should:

1. Check out the repo.
2. Install `mkdocs` and `mkdocs-material` per `docs/requirements.txt`.
3. Run `mkdocs build` using `mkdocs.yml`.
4. Publish the result.

A successful build lands at `https://google-photo-book.readthedocs.io/`
(the exact subdomain matches the project slug you confirmed in step 2 —
check the project's **Overview** page if you're not sure what it landed
on).

## 4. If the build fails

Open the failed build's log from the **Builds** tab — it's the same
`mkdocs build` command you can run locally to reproduce:

```sh
uv run --with-requirements docs/requirements.txt mkdocs build
```

The most likely causes, given this project's setup:

- A typo in `mkdocs.yml`'s `nav` pointing at a page that doesn't exist.
- A new doc page added under `docs/` but not added to `nav` (won't fail
  the build, but won't appear in the site either — check the built output
  under **Builds → View docs** if a page seems to be missing).

## 5. Ongoing maintenance

- Every push to `main` rebuilds the site automatically (via the webhook
  from step 2) — no manual redeploy step.
- Pull request previews aren't enabled by default; turn them on under the
  project's **Settings → Pull Requests** if you want a preview build per
  PR.
- To add a new doc page: create the `.md` file under `docs/`, add it to
  `mkdocs.yml`'s `nav` list, commit, and push — the next automatic build
  picks it up.
