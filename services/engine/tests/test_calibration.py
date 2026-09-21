from dantex.calibration import CalibrationSample, calibration_bands


def test_small_sample_never_becomes_publishable_probability():
    samples = [CalibrationSample(72, True) for _ in range(20)]
    band = next(b for b in calibration_bands(samples) if b.lower == 70)
    assert band.observed_rate == 100
    assert not band.publishable


def test_sufficient_band_can_be_evaluated_for_publication():
    samples = [CalibrationSample(72, i % 2 == 0) for i in range(100)]
    band = [b for b in calibration_bands(samples) if b.lower == 70][0]
    assert band.samples == 100
    assert band.publishable
    assert band.observed_rate == 50
