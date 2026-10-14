import pathlib,sys,unittest,datetime as dt
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from update_lightning import grouped_coverage, utcnow,unavailable
class CoverageTests(unittest.TestCase):
 def test_recent_contiguous_products_can_qualify(self):
  now=utcnow()
  start=now-dt.timedelta(minutes=39)
  intervals=[(start,start+dt.timedelta(minutes=10)),(start+dt.timedelta(minutes=10),start+dt.timedelta(minutes=20)),(start+dt.timedelta(minutes=20),start+dt.timedelta(minutes=30))]
  self.assertIsNotNone(grouped_coverage(intervals,now))
 def test_missing_recent_products_cannot_qualify(self):
  now=utcnow();start=now-dt.timedelta(hours=2)
  self.assertIsNone(grouped_coverage([(start,start+dt.timedelta(minutes=40))],now))
 def test_short_observation_cannot_qualify(self):
  now=utcnow()
  self.assertIsNone(grouped_coverage([(now-dt.timedelta(minutes=4),now)],now))
 def test_gaps_cannot_be_marked_complete(self):
  now=utcnow();a=now-dt.timedelta(minutes=24)
  self.assertIsNone(grouped_coverage([(a,a+dt.timedelta(minutes=10)),(a+dt.timedelta(minutes=15),now)],now))
 def test_error_is_not_empty_safe_feed(self):
  x=unavailable(utcnow(),'error')
  self.assertFalse(x['complete']);self.assertIsNone(x['observation_end'])
if __name__=='__main__':unittest.main()
