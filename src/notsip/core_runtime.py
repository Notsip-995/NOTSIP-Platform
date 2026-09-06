from .app import app,settings,auth,pairing,nodes,recovery,store,agent,events,accounts,maintenance,DATA,native_voice
from .product_routes import attach as attach_product
attach_product(app,require_auth=__import__('notsip.app',fromlist=['require_auth']).require_auth,settings=settings,auth=auth,pairing=pairing,nodes=nodes,recovery=recovery,store=store,agent=agent,events=events,accounts=accounts,maintenance=maintenance,DATA=DATA,native_voice=native_voice)
__all__=['app']
