"""Export a shareable AI-diagram brief from existing code, without DB access."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import re
import zipfile

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/ai-diagram-brief'
DATE=datetime.now(timezone.utc).date().isoformat()
DDL=ROOT/'db/migrations/001_schema.sql'
FONT=Path('/usr/share/fonts/truetype/dejavu')
COMMON={'attribute_sha256','lineage_id','source_cut','created_run_id','last_changed_run_id'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema():
    text=DDL.read_text()
    result={}
    pattern=r'CREATE TABLE warehouse_store\.(\w+) \((.*?)^\);'
    for name,body in re.findall(pattern,text,re.M|re.S):
        columns=[]
        for line in body.splitlines():
            m=re.match(r'    ([a-z_][a-z0-9_]*)\s+(timestamp without time zone|numeric\(\d+,\d+\)|char\(\d+\)|bigint|integer|smallint|uuid|text|boolean|date|numeric)(?=\s|,|$)(.*)',line)
            if m:
                columns.append({'name':m[1],'type':m[2],'not_null':'NOT NULL' in m[3]})
        pk=[x.strip() for x in re.search(r'PRIMARY KEY \(([^)]+)\)',body)[1].split(',')]
        unique=[[x.strip() for x in group.split(',')] for group in re.findall(r'^    UNIQUE \(([^)]+)\)',body,re.M)]
        fks=[]
        for source,target,fields in re.findall(r'FOREIGN KEY \(([^)]+)\) REFERENCES warehouse_store\.(\w+) \(([^)]+)\)',body):
            fks.append({'columns':[x.strip() for x in source.split(',')],'target':target,'target_columns':[x.strip() for x in fields.split(',')]})
        result[name]={'columns':columns,'primary_key':pk,'unique_business_keys':unique,'dimension_foreign_keys':fks}
    model=json.loads((ROOT/'contracts/warehouse-model.json').read_text())
    assert set(result)=={x['name'] for x in model['dimensions']+model['facts']}
    assert sum(len(t['dimension_foreign_keys']) for t in result.values())==19
    for f in model['facts']:
        actual={fk['columns'][1]:fk['target']+'.'+fk['target_columns'][1] for fk in result[f['name']]['dimension_foreign_keys']}
        assert actual==f['foreign_keys']
    for name,t in result.items():
        cols={c['name']:c for c in t['columns']}
        assert len(cols)==len(t['columns']) and set(t['primary_key'])<=set(cols)
        for fk in t['dimension_foreign_keys']:
            assert fk['columns'][0]==fk['target_columns'][0]=='release_id'
            parent={c['name']:c for c in result[fk['target']]['columns']}
            for child,target in zip(fk['columns'],fk['target_columns']):
                assert cols[child]['type']==parent[target]['type']
        assert not name.startswith('dim_') or len(t['columns'])>=9
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=schema()
    prompts=(ROOT/'docs/demo/ai-diagram-prompts.md').read_text()
    sections={key:prompts.split('## '+title+'\n',1)[1].split('\n## ',1)[0].strip()
              for key,title in [('architecture','Architecture prompt'),('erd','ERD prompt'),('review','Review prompt')]}
    for name,body in sections.items():
        (OUT/(name+'-prompt.md')).write_text(body+'\n')
    (OUT/'all-prompts.md').write_text(prompts)
    document={'scope':'Ten analytical Warehouse tables; all physical columns; only nineteen dimensional FK roles are drawn',
              'database':'sales_dw','schema':'warehouse_store','source_migration':'db/migrations/001_schema.sql',
              'ddl_sha256':sha(DDL),'external_fk_note':'References to ops and landing are outside this analytical diagram; not exported as dimensional relationships',
              'tables':data}
    (OUT/'schema-reference.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    erd=['erDiagram']
    for name,t in data.items():
        erd.append('    '+name+' {')
        fkcols={c for fk in t['dimension_foreign_keys'] for c in fk['columns']}
        for col in t['columns']:
            typ=col['type'].replace('timestamp without time zone','timestamp')
            typ=re.sub(r'\(.*\)','',typ)
            marker=' PK' if col['name'] in t['primary_key'] else (' FK' if col['name'] in fkcols else '')
            note=col['type']+('; not null' if col['not_null'] else '; nullable')
            erd.append(f'        {typ} {col["name"]}{marker} "{note}"')
        erd.append('    }')
    for name,t in data.items():
        for fk in t['dimension_foreign_keys']:
            erd.append(f'    {fk["target"]} ||--o{{ {name} : "{fk["columns"][1]}"')
    (OUT/'warehouse-full-schema.mmd').write_text('\n'.join(erd)+'\n')

    for name,file in [('Sans','DejaVuSans.ttf'),('Sans-Bold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
    pdfmetrics.registerFontFamily('Sans',normal='Sans',bold='Sans-Bold',italic='Sans',boldItalic='Sans-Bold')
    st={
        'title':ParagraphStyle('title',fontName='Sans-Bold',fontSize=23,leading=30,spaceAfter=16),
        'h1':ParagraphStyle('h1',fontName='Sans-Bold',fontSize=17,leading=23,spaceAfter=13),
        'h2':ParagraphStyle('h2',fontName='Sans-Bold',fontSize=11,leading=15,spaceAfter=7,spaceBefore=7),
        'p':ParagraphStyle('p',fontName='Sans',fontSize=9.7,leading=14.5,spaceAfter=9),
        'small':ParagraphStyle('small',fontName='Sans',fontSize=8.6,leading=12,spaceAfter=7),
        'cell':ParagraphStyle('cell',fontName='Sans',fontSize=8.1,leading=10.4),
        'mono':ParagraphStyle('mono',fontName='Mono',fontSize=7.8,leading=10.4),
    }
    story=[]; text=[]
    def p(value,style='p'):
        story.append(Paragraph(escape(value).replace('\n','<br/>'),st[style]));text.append(value+'\n')
    def h(value):p(value,'h2')
    def table(rows,widths=None,mono_first=False):
        cells=[[Paragraph(escape(str(c)),st['mono'] if mono_first and j==0 and i>0 else st['cell']) for j,c in enumerate(row)] for i,row in enumerate(rows)]
        width=A4[0]-86
        widths=widths or [1/len(rows[0])]*len(rows[0])
        t=Table(cells,colWidths=[width*w for w in widths],repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF1FD')),
             ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#D9D9D9')),
             ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),6),
             ('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        story.extend([t,Spacer(1,8)])
        text.append('\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n')
    def new(title):
        story.append(PageBreak());text.append('\n---\n');p(title,'h1')
    def columns(name):
        t=data[name];h(name)
        fkcols={c for fk in t['dimension_foreign_keys'] for c in fk['columns']}
        rows=[['Column','PostgreSQL type','Key','Null']]
        for col in t['columns']:
            if col['name'] in COMMON:continue
            markers=[]
            if col['name'] in t['primary_key']:markers.append('PK')
            if col['name'] in fkcols:markers.append('FK')
            rows.append([col['name'],col['type'],' / '.join(markers) or '-', 'NN' if col['not_null'] else 'nullable'])
        table(rows,[.46,.29,.12,.13],True)

    p('SalesDW Diagram Generation Brief','title')
    p('Thông tin để AI tạo hình kiến trúc và ERD theo ảnh mẫu','h1')
    p('Bản '+DATE+'. Đây là brief cho hai ảnh kỹ thuật, không phải bản báo cáo dự án trước đó. Ảnh mẫu chỉ là tham chiếu phong cách; tên bảng, công nghệ và đường nối phải lấy từ tài liệu này.')
    h('Cách dùng')
    p('1. Tải PDF này cùng hai ảnh mẫu lên công cụ AI bạn chọn.\n2. Yêu cầu tạo hình kiến trúc trước bằng Architecture prompt ở trang 2.\n3. Tạo ERD riêng bằng ERD prompt ở trang 3.\n4. Nếu công cụ nhận file, đính kèm schema-reference.json hoặc warehouse-full-schema.mmd để giữ đúng tên cột và quan hệ.\n5. Dùng Review prompt ở trang cuối để kiểm trước khi xuất.')
    h('Sự thật phải giữ nguyên')
    table([['Hạng mục','Nội dung'],['Tên dự án','Sales and Customer Analytics Warehouse'],['Phạm vi','Portfolio độc lập; Olist công khai; Docker local; không phải kiến trúc nội bộ Abbott/Concentrix'],['Stack có thật','Python, MinIO, PostgreSQL, dbt Core, local MetricFlow, Apache Airflow, Apache Superset'],['Nguồn','Olist v2 snapshot: 7 CSV feeds, 451.535 dòng, 99.441 orders'],['DWH','Kimball: 7 dimensions + 3 facts; integer dimension SK; conformed dimensions'],['Đầu ra','8 KPI lõi, 5 MetricFlow exports, 6 dashboard, SQL/notebook'],['Không có trong v1','OLTP riêng, CDC, streaming, Kafka/Spark/Trino/Iceberg/Delta, telesales, HA']], [.24,.76])
    p('File không chứa mật khẩu, connection strings, raw data hoặc thông tin nội bộ. PDF là nguồn thông tin; chất lượng chữ và quan hệ trong ảnh do AI sinh vẫn cần kiểm lại. Đối với ERD dày chữ, ưu tiên SVG/diagram code chỉnh sửa được thay vì chỉ một ảnh raster.','small')

    new('1 Architecture prompt')
    p('Copy nguyên phần tiếng Anh dưới đây; kèm ảnh mẫu kiến trúc.','small')
    for paragraph in sections['architecture'].split('\n\n'):p(paragraph)

    new('2 ERD prompt')
    p('Copy nguyên phần tiếng Anh dưới đây; kèm ảnh mẫu database schema. Các trang sau cung cấp cột và quan hệ chính xác.','small')
    for paragraph in sections['erd'].split('\n\n'):p(paragraph)

    new('3 Dimension columns phần một')
    p('Các bảng đều thuộc warehouse_store. PK là composite gồm release_id và key. NN = NOT NULL. Audit columns chung được gom ở trang kế; JSON/Mermaid giữ toàn bộ cột.','small')
    for name in ['dim_customer','dim_product','dim_seller']:columns(name)

    new('4 Dimension columns và metadata chung')
    for name in ['dim_buyer_geography','dim_date','dim_order_status','dim_payment_method']:columns(name)
    h('Metadata vật lý được gom để hình dễ đọc')
    p('Mọi bảng có lineage_id uuid, source_cut bigint, created_run_id uuid và last_changed_run_id uuid. Các dimensions còn có attribute_sha256 text. lineage_id nullable trong dimensions và NOT NULL trong facts; các trường kỹ thuật còn lại NOT NULL. Các FK của metadata trỏ tới ops/landing nằm ngoài core ERD này. Không vẽ chúng thành quan hệ dimension-fact.','small')
    p('Olist thực tế chỉ có snapshot; valid_from/valid_to của product là capability contract, không phải bằng chứng có lịch sử SCD2 thật. customer_unique_id là identity khách; buyer geography giữ ngữ cảnh địa chỉ của đơn. Không thêm tên khách/sản phẩm.','small')

    new('5 Order fact accumulating snapshot')
    p('fct_orders: một dòng cho (source_system, order_id). Physical PK = (release_id, order_key); unique business grain = (release_id, source_system, order_id). Giữ order khi thiếu items/payment, kèm flags. order_id là degenerate dimension.','small')
    columns('fct_orders')
    p('Năm date FK cùng trỏ dim_date; timestamp không có timezone offset. Tiền là numeric/Decimal. Không SUM child totals sau khi join vào nhiều atomic item/payment rows. Audit columns chung ở trang 5 và file JSON.','small')

    new('6 Transaction facts')
    p('Mỗi fact giữ grain độc lập; không có fact-to-fact FK. Release_id là một phần PK và mọi dimensional FK.','small')
    columns('fct_order_items')
    columns('fct_payments')
    p('Items unique: release + source + order_id + order_item_id. Payments unique: release + source + order_id + payment_sequential. order_item_id là line ordinal, không phải quantity; payment_installments không phải measure cộng dồn. Purchase date trên payment là ngữ cảnh đơn, không phải payment event time.','small')

    new('7 Danh sách chính xác 19 FK roles')
    p('Tất cả connector biểu diễn (release_id, fact_role_key) → (release_id, dimension_key). Crow’s foot ở phía fact; một dimension member có thể được nhiều fact rows tham chiếu. Không nối facts chỉ vì cùng order_id.','small')
    rows=[['Fact','FK role','Dimension']]
    for name,t in data.items():
        for fk in t['dimension_foreign_keys']:rows.append([name,fk['columns'][1],fk['target']])
    table(rows,[.25,.40,.35],True)
    h('Grain và business identity')
    table([['Fact','Grain không gồm technical release'],['fct_orders','source_system + order_id'],['fct_order_items','source_system + order_id + order_item_id'],['fct_payments','source_system + order_id + payment_sequential']], [.3,.7])
    p('Fact keys order_key/order_item_key/payment_key là text trong implementation; chỉ dimension SKs là warehouse-managed integer. Reserved members: 0 Unknown, -1 N/A. Inferred members giữ integer SK khi bổ sung attributes.','small')

    new('8 Control data flow và kiểm ảnh')
    h('Node và mũi tên kiến trúc không được tự đổi')
    table([['Quan hệ','Ý nghĩa'],['Olist → Python → MinIO','Giữ source-native raw và checksum; không làm giàu dữ liệu tại MinIO'],['MinIO → Python → landing','Đọc/replay raw; validate trước admission; accepted source versions và fixed source_cut'],['landing → dbt → work','Staging/intermediate; 7 dims, 3 facts; tests và registry'],['work → controlled snapshot → warehouse_store','Copy đầy đủ vào immutable release; FK/grain/reconciliation gates'],['warehouse_store → semantic_input → MetricFlow → reporting','Bind release trên từng connection; execute SQL; lưu 5 metric exports'],['published Kimball → reporting.analytic_*','SQL views cho customer/cohort/delivery/payment, không giả là MetricFlow metrics'],['publication gate → published reporting → Superset','Chỉ khi checks/parity đạt; readonly và mọi chart pin cùng release'],['Airflow - - → execution tasks','Dashed control arrows; raw/validate/load/lease/build/snapshot/semantic/publish/finish']], [.47,.53])
    h('Review prompt')
    p(sections['review'])
    p('Checklist: đúng 10 bảng; đúng datatype và 19 FK roles; không fact-to-fact; không gộp PostgreSQL schemas thành nhiều DWH; không native Superset–MetricFlow API; không tự thêm stack trong ảnh mẫu. Official logos chỉ là nhãn công nghệ, không ngụ ý affiliation. Không dùng logo Abbott/Concentrix.','small')
    p('Sources: infra/compose.yaml; orchestration/dags/sales_warehouse_pipeline.py; contracts/warehouse-model.json; db/migrations/001_schema.sql và 005_published_analysis.sql; src/sales_dw/export_metrics.py; README.md. Schema JSON giữ SHA-256 migration. Đây là tài liệu đọc từ code, không chạy DDL/SQL hoặc tái nghiệm thu runtime.','small')

    (OUT/'brief.md').write_text('\n'.join(text))
    def header(canvas,doc):
        canvas.setFont('Sans',8);canvas.setFillColor(colors.HexColor('#52647B'))
        canvas.drawString(43,A4[1]-26,'SALESDW | AI DIAGRAM BRIEF')
        canvas.drawRightString(A4[0]-43,A4[1]-26,DATE)
        canvas.setStrokeColor(colors.HexColor('#D9D9D9'));canvas.line(43,35,A4[0]-43,35)
        canvas.drawString(43,22,'Independent Olist portfolio | Local demo | Not internal Abbott / Concentrix')
        canvas.drawRightString(A4[0]-43,22,str(doc.page))
    pdf=OUT/'diagram-generation-brief.pdf'
    doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=43,rightMargin=43,topMargin=47,bottomMargin=47,title='SalesDW Architecture and ERD Generation Brief')
    doc.build(story,onFirstPage=header,onLaterPages=header)
    pages=len(PdfReader(pdf).pages)
    assert pages==9,('Unexpected page count',pages)
    (OUT/'README.md').write_text('''# AI diagram brief

Upload diagram-generation-brief.pdf and the two reference images to your chosen AI. Ask for architecture and ERD as two separate images. architecture-prompt.md, erd-prompt.md and review-prompt.md are ready to copy. For exact tables/columns, use schema-reference.json or warehouse-full-schema.mmd. The source of truth is the existing implementation, not the reference images.

The schema files contain all physical columns from the ten Warehouse tables and nineteen dimensional FK roles. References to ops/landing are outside this analytical diagram. PDF tables collapse common technical audit columns explicitly; JSON/Mermaid do not omit them. No business data, secrets or internal enterprise information are included.

Regenerate from project root: python scripts/build_ai_diagram_brief.py. Document dependencies: reportlab and pypdf; font DejaVu Sans. This exporter never connects to a database or starts services. The PDF is a generation brief, not a promise that a third-party image model will preserve dense ERD labels correctly.
''')
    manifest={'date':DATE,'pdf_pages':pages,'tables':len(data),'columns':sum(len(t['columns']) for t in data.values()),
              'dimensional_fk_roles':19,'migration_sha256':sha(DDL),'scope':'Offline diagram authoring only; no runtime/migration/data changes',
              'output_sha256':{str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(ROOT/'output/ai-diagram-brief.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()):
            if p.is_file():z.write(p,'ai-diagram-brief/'+p.name)
        assert z.testzip() is None
    print(json.dumps({'passed':True,'pdf_pages':pages,'tables':len(data),'columns':manifest['columns'],'dimensional_fk_roles':19,'pdf':str(pdf)}))


if __name__=='__main__':main()
