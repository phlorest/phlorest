def test_valid(cldf_dataset, cldf_logger):
    assert cldf_dataset.validate(log=cldf_logger)


def test_phlorest_check(cldf_dataset, cldf_logger):
    from phlorest.check import run_checks
    assert run_checks(cldf_dataset, cldf_logger)
