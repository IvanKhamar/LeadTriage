from app.ratelimit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window_s=60, clock=clock)

    assert limiter.retry_after("1.2.3.4") == 0
    assert limiter.retry_after("1.2.3.4") == 0
    assert limiter.retry_after("1.2.3.4") > 0
    assert limiter.retry_after("5.6.7.8") == 0  # other IPs are not affected

    clock.now += 61
    assert limiter.retry_after("1.2.3.4") == 0
