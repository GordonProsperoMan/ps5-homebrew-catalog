# Review policy

How maintainers decide what is listed and how listings change over time.

## What a listing means

An app is listed when:

1. every automated check passes (see [Automation](automation.md)), and
2. a maintainer has reviewed the submission as described below.

A listing is **not** a security audit of the app's code. The catalog guarantees
that users receive exactly the reviewed bytes from the stated source repository,
under the stated title ID and publisher.

## Maintainer review

Before merging a submission, a maintainer confirms:

- **Publisher.** The submitter owns the source repository (automated), and the
  `author` field credibly names the developer rather than someone else's brand.
- **Provenance.** The repository contains the app's source, or clearly states
  where it lives. Repackaged or rebranded copies of someone else's app are not
  listed without the original developer's consent.
- **Honesty.** The name, description, kind and icon describe the app accurately
  and don't imitate another listing or an official product.
- **Scope.** The app is PS5 homebrew. Pirated commercial content, tools whose
  main purpose is piracy, malware and apps that exfiltrate user data are refused.
- **License.** The license allows redistribution of the published build.

Maintainers may ask questions on the pull request and decline submissions that
don't meet this policy.

## Title IDs

- Title IDs are first come, first served; the first merged record owns the ID.
- Only the owner of the listed `source_repo` can update a record (automated).
- An app can move to a new repository owner only through a maintainer, usually
  after the current owner confirms in an ownership transfer issue.
- If a listed title ID is shown to belong to an earlier, widely distributed app
  by another developer, maintainers resolve the dispute case by case and may ask
  the newer app to change its ID.

## Reservations

A reservation (`"status": "coming-soon"`) holds a title ID for an unreleased
app and shows it as coming soon.

- Only the owner of the reservation's `source_repo` can create it, update it,
  or turn it into a release (automated).
- Each publisher can hold up to 5 reservations (automated).
- A reservation that hasn't changed for 180 days is flagged by the weekly
  health check. Maintainers ask the owner in an issue and release the title ID
  if there's no reply within 14 days.
- Reservations get the same honesty and scope review as listings: no
  impersonation, no squatting on other projects' names or IDs.

## Updates

Updates follow the same checks and ownership rule as new listings. Maintainers
review whether the new release still matches the listing; a change of
repository, publisher or purpose is treated like a new submission.

## Broken and stale listings

The weekly health check re-verifies every listing.

- **Missing release, asset or icon, or a changed sha256:** maintainers contact
  the owner through an issue. If a replacement or explanation doesn't arrive
  within 14 days, the listing is withdrawn. A changed sha256 on a listed asset
  is treated as a security incident: the listing is withdrawn immediately and
  restored only after the owner explains the change.
- **Newer upstream release:** reported for information. Owners update their
  records with a pull request; maintainers don't update records on their behalf.

## Withdrawals

A listing is withdrawn when:

- its owner requests it (withdrawal issue from the owning account),
- it breaks and isn't fixed (above),
- it is found to be malicious or compromised (see [SECURITY.md](../SECURITY.md)),
  or
- it violates this policy or a valid legal request.

Withdrawal removes the record from `main`; the website and feed follow on the
next build. The artifact itself stays under its developer's control.
