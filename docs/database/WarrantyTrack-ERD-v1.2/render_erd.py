from graphviz import Digraph
from html import escape
from pathlib import Path
P=Path(__file__).resolve().parent
COL={'identity':'#5B21B6','assets':'#123B7A','catalog':'#0E7490','warranty':'#B45309','files':'#0F766E','draft':'#7C3AED','notifications':'#166534','muted':'#334155'}
INK='#142238'; LINE='#D3DFEA'

def card(name,category,fields,subtitle=None):
    color=COL[category]
    rows=[f'<TR><TD BGCOLOR="{color}" ALIGN="LEFT" COLSPAN="2" CELLPADDING="12"><FONT FACE="DejaVu Sans" COLOR="#FFFFFF" POINT-SIZE="16"><B>{escape(name)}</B></FONT></TD></TR>']
    if subtitle:rows.append(f'<TR><TD BGCOLOR="#EAF0F7" ALIGN="LEFT" COLSPAN="2" CELLPADDING="6"><FONT FACE="DejaVu Sans" COLOR="{INK}" POINT-SIZE="10">{escape(subtitle)}</FONT></TD></TR>')
    for i,(key,field) in enumerate(fields):
        bg='#FFFFFF' if i%2==0 else '#F1F5F9'
        badgecolor='#1D4ED8' if key=='PK' else '#0F766E' if key=='FK' else '#475569' if key=='REQ' else '#64748B'
        rows.append(f'<TR><TD ALIGN="CENTER" BGCOLOR="{bg}" WIDTH="48"><FONT FACE="DejaVu Sans" COLOR="{badgecolor}" POINT-SIZE="10"><B>{escape(key or "·")}</B></FONT></TD><TD ALIGN="LEFT" BGCOLOR="{bg}" WIDTH="265"><FONT FACE="DejaVu Sans" COLOR="{INK}" POINT-SIZE="11">{escape(field)}</FONT></TD></TR>')
    return f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0" COLOR="{LINE}" BGCOLOR="#FFFFFF">{"".join(rows)}</TABLE>>'

def create(title, filename):
    g=Digraph(name=filename,format='svg',engine='dot')
    g.attr(rankdir='LR',bgcolor='#F6F9FC',pad='0.38',nodesep='0.49',ranksep='1.05',splines='polyline',outputorder='edgesfirst',newrank='true',fontname='DejaVu Sans',fontsize='24',fontcolor='#0F172A',labelloc='t',label=title)
    g.attr('node',shape='plain',fontname='DejaVu Sans')
    g.attr('edge',color='#7692AA',penwidth='1.45',arrowsize='0.7',arrowhead='vee',fontname='DejaVu Sans',fontsize='10',fontcolor='#475569')
    return g

def edge(g,from_,to,label=None,color=None):
    kw={}
    if label:kw['xlabel']=label
    if color:kw['color']=color
    g.edge(from_,to,**kw)

core=create('WarrantyTrack | ERD 01  ·  Identity, Assets & Warranties','warrantytrack_erd_core')
entities={
 'users':('USERS','identity',[('PK','id : uuid'),('','cognito_sub : text !'),('','email : citext !'),('','display_name : text !')],'Amazon Cognito account mapping'),
 'organizations':('ORGANIZATIONS','identity',[('PK','id : uuid'),('FK','created_by → users'),('','name : text !')],None),
 'organization_members':('ORG_MEMBERS','identity',[('PK','organization_id + user_id'),('FK','organization_id → organizations'),('FK','user_id → users'),('','role : admin | employee'),('','member_status : text')],None),
 'categories':('CATEGORIES','catalog',[('PK','id : uuid'),('','name : text !')],None),
 'vendors':('VENDORS','catalog',[('PK','id : uuid'),('','name : text !'),('','website_url : text ?')],None),
 'departments':('DEPARTMENTS','catalog',[('PK','id : uuid'),('FK','organization_id → organizations'),('','name : text !')],None),
 'locations':('LOCATIONS','catalog',[('PK','id : uuid'),('FK','organization_id → organizations'),('','name : text !'),('','description : text ?')],None),
 'assets':('ASSETS','assets',[('PK','id : uuid'),('FK','personal_owner_user_id ?'),('FK','organization_id ?'),('FK','created_by → users'),('FK','assigned_to_user_id ?'),('FK','vendor_id / category_id !'),('FK','department_id / location_id ?'),('REQ','product_name : text !'),('REQ','purchase_date : date !'),('REQ','purchase_price : numeric !'),('REQ','serial_number : text !'),('FK','primary_warranty_id : uuid !'),('REQ','invoice_number : text !'),('','storage_note : text ?')],'exactly one owner: personal OR org'),
 'warranties':('WARRANTIES','warranty',[('PK','id : uuid'),('FK','asset_id → assets'),('REQ','provider_name : text !'),('REQ','starts_on : date !'),('REQ','expires_on : date !'),('REQ','duration_months : int !'),('','warranty_type : text !'),('','coverage_details : text ?')],'1..N warranties required per asset'),
 'documents':('DOCUMENTS','files',[('PK','id : uuid'),('FK','asset_id → assets'),('FK','uploaded_by → users'),('','document_kind : text !'),('REQ','s3_bucket / s3_key !'),('','mime_type : text !'),('','size_bytes : bigint !')],'metadata only; bytes live in S3'),
}
for id,(name,cat,fields,sub) in entities.items():core.node(id,card(name,cat,fields,sub))
for a,b,l in [
 ('organizations','users','creator'),('organization_members','organizations','membership'),('organization_members','users','member'),
 ('departments','organizations',None),('locations','organizations',None),
 ('assets','users','personal / creator'),('assets','organizations','org'),('assets','organization_members','assignee'),
 ('assets','categories',None),('assets','vendors',None),('assets','departments',None),('assets','locations',None),
 ('warranties','assets','N:1'),('assets','warranties','primary warranty'),('documents','assets','N:1'),('documents','users','uploaded by')]:edge(core,a,b,l)
core.render(str(P/'warrantytrack_erd_core'),cleanup=True)

flow=create('WarrantyTrack | ERD 02  ·  Add Asset OCR Workflow & Alerts','warrantytrack_erd_workflow')
extra={
 'users':('USERS','muted',[('PK','id : uuid'),('','account / recipient')],'Reference from ERD 01'),
 'assets':('ASSETS','assets',[('PK','id : uuid'),('','committed only after review'),('REQ','serial_number : required'),('','storage_note : nullable'),('FK','primary_warranty_id : required')],'Reference from ERD 01'),
 'asset_drafts':('ASSET_DRAFTS','draft',[('PK','id : uuid'),('FK','created_by → users'),('FK','personal_owner_user_id ?'),('FK','organization_id ?'),('FK','completed_asset_id ?'),('','current_step : 1..3'),('','entry_method : upload/camera/manual'),('','draft_status : text !'),('','receipt_review_confirmed : bool'),('','serial_review_confirmed : bool'),('','draft_payload : jsonb !')],'editable data before final commit'),
 'draft_files':('DRAFT_FILES','files',[('PK','id : uuid'),('FK','draft_id → asset_drafts'),('FK','uploaded_by → users'),('','file_kind : receipt / serial / box'),('REQ','s3_bucket / s3_key !'),('','mime_type : text !')],'optional when manually entered'),
 'ocr_extractions':('OCR_EXTRACTIONS','draft',[('PK','id : uuid'),('FK','draft_file_id → draft_files'),('','extraction_kind : receipt / serial'),('','provider : aws_textract'),('','ocr_status : text !'),('','extracted_fields : jsonb !'),('','raw_result : jsonb ?')],'review / correct before confirm'),
 'documents':('DOCUMENTS','files',[('PK','id : uuid'),('FK','asset_id → assets'),('','document_kind : text !'),('','S3 object metadata')],'committed file records'),
 'warranties':('WARRANTIES','warranty',[('PK','id : uuid'),('FK','asset_id → assets'),('REQ','provider / dates / months !')],'1..N required per asset'),
 'notification_preferences':('NOTIFICATION_PREFS','notifications',[('PK','user_id → users'),('','email_enabled : bool'),('','in_app_enabled : bool'),('','warning_days : smallint')],None),
 'notifications':('NOTIFICATIONS','notifications',[('PK','id : uuid'),('FK','recipient_user_id → users'),('FK','asset_id → assets ?'),('FK','warranty_id → warranties ?'),('','notification_type : text !'),('','read_at : timestamptz ?')],None),
 'notification_deliveries':('NOTIFICATION_DELIVERIES','notifications',[('PK','id : uuid'),('FK','notification_id → notifications'),('','channel : email'),('','delivery_status : text !'),('','ses_message_id : text ?')],'Amazon SES delivery attempts'),
}
for id,(name,cat,fields,sub) in extra.items():flow.node(id,card(name,cat,fields,sub))
for a,b,l in [
 ('asset_drafts','users','author'),('asset_drafts','assets','on complete'),
 ('draft_files','asset_drafts','upload'),('draft_files','users',None),
 ('ocr_extractions','draft_files','OCR result'),
 ('documents','assets','N:1'),('warranties','assets','N:1'),('assets','warranties','primary warranty'),
 ('notification_preferences','users','1:1'),('notifications','users','recipient'),
 ('notifications','assets','asset'),('notifications','warranties','warranty'),
 ('notification_deliveries','notifications','email')]:edge(flow,a,b,l)
flow.render(str(P/'warrantytrack_erd_workflow'),cleanup=True)
# render PNG high resolution via graphviz directly from generated source
for g,name in ((core,'warrantytrack_erd_core'),(flow,'warrantytrack_erd_workflow')):
    g.format='png';g.graph_attr['dpi']='170';g.render(str(P/name),cleanup=True)
print('Generated:')
for p in P.glob('*'):
 if p.suffix in ('.png','.svg'):
  print(p.name,p.stat().st_size)
