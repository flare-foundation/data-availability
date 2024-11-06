from django.test import TestCase

from ftso.models import FeedResult, RandomResult


class FeedResultTestCase(TestCase):
    def setUp(self):
        FeedResult.objects.create(
            pk=1,
            voting_round_id=1,
            feed_id="014144412f55534400000000000000000000000000",
            value=1000,
            turnout_bips=8500,
            decimals=2,
        )
        FeedResult.objects.create(
            id=2,
            voting_round_id=667713,
            feed_id="01414156452f555344000000000000000000000000",
            value=851010,
            turnout_bips=0,
            decimals=4,
        )
        RandomResult.objects.create(
            id=1,
            voting_round_id=667713,
            value="4e5961cc8e1bb59e64d5190ae1fde439ef4e8153deb4434437dd76c43e59d20a",
            is_secure=True,
        )

    def test_feed_result_representation_1(self):
        feed_result = FeedResult.objects.get(pk=1)
        self.assertEqual(feed_result.representation, "ADA/USD")

    def test_feed_result_representation_2(self):
        feed_result = FeedResult.objects.get(pk=2)
        self.assertEqual(feed_result.representation, "AAVE/USD")

    def test_feed_result_type(self):
        feed_result = FeedResult.objects.get(pk=1)
        self.assertEqual(feed_result.type, 1)

    def test_feed_result_timestamp(self):
        feed_result = FeedResult.objects.get(pk=1)
        self.assertEqual(feed_result.timestamp, 1658430135)

    def test_feed_result_hash_1(self):
        feed_result = FeedResult.objects.get(pk=1)
        self.assertEqual(
            feed_result.hash.hex(),
            "0x3340586f8ba8a0d651564de8b7615fa1f9f114ac24768e6dbc9ee055d1552372",
        )

    def test_feed_result_hash_2(self):
        feed_result = FeedResult.objects.get(pk=2)
        self.assertEqual(
            feed_result.hash.hex(),
            "0x2cc51313f84c3da21d55bb4e4c52f8761d86e50fc867b78585db28d59fff0023",
        )

    def test_random_result_hash(self):
        random_result = RandomResult.objects.get(pk=1)
        self.assertEqual(
            random_result.hash.hex(),
            "0x20542916096759045c2e8f7676f4d73c2fc4fe2297dd5f7fa37d1ae883ad7eb2",
        )
