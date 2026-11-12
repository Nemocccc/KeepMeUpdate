import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_report as report
import install_local
import rss_fetch
from verify_links import is_paywalled


class NewsTests(unittest.TestCase):
    def evidence(self):
        return {'articles': [dict(id=str(i), title=f'Event {i}', evidence=f'Confirmed event {i}',
            url=f'https://example.org/{i}', source='example.org', feed='Example',
            published_at='2026-11-12T00:00:00+00:00') for i in range(3)]}

    def digest(self):
        return dict(title='今日新闻', articles=[dict(id=str(i), section=report.SECTIONS[0],
            headline=f'新闻{i}', summary='事实摘要', significance='值得关注',
            evidence_quote=f'event {i}') for i in range(3)], outlook=[])

    def test_publication_timezone_is_converted_not_erased(self):
        expected = '2026-11-11T23:30:00+00:00'
        self.assertEqual(rss_fetch.parse_date('Thu, 12 Nov 2026 07:30:00 +0800'), expected)
        self.assertEqual(rss_fetch.parse_date('2026-11-12T07:30:00+08:00'), expected)

    def test_missing_date_stays_unknown(self):
        articles, error = rss_fetch.parse_rss('<rss><channel><item><title>Old</title><link>https://example.org/old</link></item></channel></rss>', 'https://example.org/rss')
        self.assertIsNone(error)
        self.assertIsNone(articles[0]['date'])

    def test_atom_uses_article_not_feed_self_link(self):
        articles, _ = rss_fetch.parse_rss('''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title><link rel="self" href="https://example.org/feed"/><link rel="alternate" href="https://example.org/story"/></entry></feed>''', 'https://example.org/atom')
        self.assertEqual(articles[0]['url'], 'https://example.org/story')

    def test_identity_and_quote_are_enforced(self):
        valid = report.validate(self.digest(), self.evidence())
        self.assertEqual(valid['articles'][0]['url'], 'https://example.org/0')
        for key, value in [('id','invented'), ('evidence_quote','not in source')]:
            digest = self.digest()
            digest['articles'][0][key] = value
            with self.assertRaises(ValueError): report.validate(digest, self.evidence())

    def test_outlook_cannot_cite_unselected_news(self):
        digest = self.digest()
        digest['outlook'] = [dict(evidence_ids=['unknown'])]
        with self.assertRaises(ValueError): report.validate(digest, self.evidence())

    def test_tracking_removed_but_semantic_query_preserved(self):
        self.assertEqual(report.canonical_url('https://example.org/story?id=42&utm_source=rss#top'), 'https://example.org/story?id=42')

    def test_paywall_hostname_not_arbitrary_url_text(self):
        self.assertTrue(is_paywalled('https://www.reuters.com/news/a'))
        self.assertFalse(is_paywalled('https://example.org/reuters.com'))
        self.assertFalse(is_paywalled('https://reuters.com.example.org/news'))

    def test_link_failure_drops_only_gone_articles_and_dependent_outlook(self):
        digest = self.digest()
        digest['articles'].append(dict(id='3',url='https://example.org/3'))
        for i,a in enumerate(digest['articles']): a['url']=f'https://example.org/{i}'
        digest['outlook']=[dict(evidence_ids=['3'])]
        statuses = [dict(status=200,ok=True),dict(status=403,ok=False),dict(status=None,ok=False),dict(status=404,ok=False)]
        with patch.object(report,'check_url',side_effect=statuses): result=report.check_links(digest)
        self.assertEqual(len(result['articles']),3)
        self.assertEqual(result['outlook'],[])

    def test_cron_uses_absolute_paths_and_restores_timezone(self):
        existing='CRON_TZ=UTC\n0 * * * * rclone sync source dest\n'
        block=install_local.cron_block(existing,dict(delivery_time='08:00',timezone='Asia/Shanghai'),Path('/tmp/a b/config.json'),Path('/tmp/log'))
        self.assertIn('0 8 * * *',block)
        self.assertIn('CRON_TZ=Asia/Shanghai',block)
        self.assertIn('CRON_TZ=UTC',block)
        self.assertIn("'/tmp/a b/config.json'",block)


if __name__ == '__main__': unittest.main()
