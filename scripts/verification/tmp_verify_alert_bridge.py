import sys
import types

psycopg2_stub = types.ModuleType('psycopg2')
psycopg2_stub.paramstyle = 'pyformat'
psycopg2_stub.connect = lambda *args, **kwargs: None
psycopg2_stub.extras = types.SimpleNamespace()
sys.modules['psycopg2'] = psycopg2_stub
sys.modules['psycopg2.extras'] = psycopg2_stub.extras

from backend.alert_engine.alert_manager import get_alert_manager
from backend.api.websocket import get_broadcast_bridge

mgr = get_alert_manager()
mgr.set_broadcast_bridge(get_broadcast_bridge())
pred = {'attack_type': 'http_flood', 'confidence': 0.95, 'severity': 'high'}
flow = {'src_ip': '203.0.113.10', 'dst_ip': 'server-2', 'event_type': 'http_flood', 'count': 100}
alert = mgr.generate_alert(pred, flow)
print('generated_alert_id=', alert['alert_id'])
print('queue_size_after=', get_broadcast_bridge().get_stats()['queue_size'])
