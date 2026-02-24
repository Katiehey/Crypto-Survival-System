def test_dry_run_import():
    """Sanity test: import the dry-run script and run a short replay without errors."""
    from scripts.dry_run_paper_trading import main

    # Run with a very small limit to keep test fast
    main(limit=50, speed='instant')
