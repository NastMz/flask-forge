# 📦 Release Scripts Setup

To use the release automation scripts, you need to install additional dependencies.

## 🚀 Quick Installation

```bash
# Install development dependencies (includes those needed for scripts)
pip install -e ".[dev]"
```

## ✅ Verify Installation

```bash
# Test the wrapper script
python release.py help

# Test the main script
python scripts/forge_release.py --help
```

## 📖 Complete Documentation

See [`RELEASE_GUIDE.md`](./RELEASE_GUIDE.md) for complete documentation on how to use the scripts.

## 🎯 Basic Usage

```bash
# Interactive mode (recommended to start)
python release.py

# Direct commands
python release.py feature my-new-feature
python release.py patch
python release.py publish
```

You're ready to automate your release workflow! 🎉
