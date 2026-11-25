# Changelog

All notable changes to the bonus-bot project will be documented in this file. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-11-25

### Added

- Added a root-level `config.py` as the single place for accounts, comment/forward
  links, per-account counts, Chaohua settings and account delays.
- Added `core/runner.py`: `main.py` now provides an interactive menu and a CLI
  (`python main.py comment|forward|chaohua`, optional `--link`).
- Added automatic target registration: a new Weibo link is appended to
  `conf/comment_data.json` or `conf/forward_data.json` with counter 0 and is
  reused on subsequent runs. `link_index` is no longer needed.
- Added `core/targets.py` for link normalization, duplicate detection and data
  file management.

## [0.0.9] - 2026-11-23

### Fixed

- Fixed Weibo comments after the 2026 comment UI redesign: the sender now uses the new
  `发布你的评论` composer, the WooUI `评论` button, and the `.wbpro-list` comment items
  instead of the removed `#composerEle` markup.
- Fixed Weibo forwards after the 2026 forward UI redesign: the forwarder now clicks the
  main post's `转发` icon, uses the inline `说说分享心得` composer and `转发` button,
  clears the quoted prefill, and waits for `转发成功` before updating `forward_data.json`.
  Forward accounts also get per-account isolation.
- Added a per-account run summary for comments and forwards, showing how many
  items were sent and why an account stopped.

## [0.0.8] - 2026-11-23

### Added

- Added `account_switch_delay` (default 180 seconds) between accounts to avoid Weibo's
  "访问频繁" rate limiting.

### Fixed

- Fixed Chaohua posting after the 2026 Chaohua redesign.

## [0.0.7] - 2025-09-29

### Changed

- Add venv in project.

## [0.0.6] - 2024-11-03

### Changed

- Updated README.

## [0.0.5] - 2024-09-17

### Added

- Added the ability to register in Chaohua.

## [0.0.4] - 2024-09-16

### Added

- Added the ability to post in Chaohua.

## [0.0.3] - 2023-03-18

### Added

- Added the ability to forward Weibo.

## [0.0.2] - 2023-02-25

### Changed

- Removed unnecessary code.

## [0.0.1] - 2023-02-24

### Added

- Users can log in by scanning a QR code and saving their login information in Chrome profiles.
- Automatically leave comments (with a specified count number and random letters) and click the LIKE
  button on them. Stop automatically LIKE comments when it encounters an error.
- Automatically switch to the next account in case of expired cookies or submission failures, ensuring a seamless
  commenting experience.
