import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as patches
import io
import os
import urllib.request
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- ページ設定 (ワイド表示) ---
st.set_page_config(layout="wide", page_title="パレット積載シミュレーター")

# ログアウトボタン（ログイン中のみ表示）
if st.sidebar.button("ログアウト"):
    st.session_state.authenticated = False
    st.rerun()

# --- フォント準備 (外部コマンドを使わずPython標準機能でDL) ---
@st.cache_resource
def setup_font():
    font_path = "ipaexg.ttf"
    if not os.path.exists(font_path):
        url = "https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.zip"
        zip_name = "ipaexg00401.zip"
        try:
            # wgetの代わりにurllibを使用
            urllib.request.urlretrieve(url, zip_name)
            with zipfile.ZipFile(zip_name, 'r') as z:
                z.extractall(".")
            extracted_path = "ipaexg00401/ipaexg.ttf"
            if os.path.exists(extracted_path):
                os.replace(extracted_path, font_path)
        except Exception:
            pass # エラー時はデフォルトフォントへ
    
    # Matplotlibへの登録
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rc('font', family='IPAexGothic')
        return font_path
    return None

font_file = setup_font()

# --- トラック描画関数 (背景白固定) ---
def create_horizontal_trucks_figure(num_pallets):
    # figsizeをラボ版に近い比率に
    fig, ax = plt.subplots(2, 1, figsize=(6, 3))
    # 背景を白に固定（ダークモード対策）
    fig.patch.set_facecolor('white')

    SCALE = 1/100
    PALLET_W = 1100 * SCALE
    PALLET_D = 1100 * SCALE
    TRUCK_W_BODY = 2400 * SCALE
    MARGIN = 50 * SCALE
    MAX_L_10T = 9600 * SCALE
    CABIN_L = 1500 * SCALE

    LIMIT_X_MIN = -CABIN_L - 10
    LIMIT_X_MAX = MAX_L_10T + 20
    LIMIT_Y_MIN = -15
    LIMIT_Y_MAX = TRUCK_W_BODY + 20

    def draw_truck_h(ax_obj, truck_type, max_p, current_p):
        ax_obj.set_facecolor('white') # 軸背景も白
        if truck_type == '4t':
            TRUCK_L = 6200 * SCALE
            color_cab = '#87CEEB'
            label = "4t (Max 10)"
        else:
            TRUCK_L = 9600 * SCALE
            color_cab = '#FFB6C1'
            label = "10t (Max 16)"

        ax_obj.set_xlim(LIMIT_X_MIN, LIMIT_X_MAX)
        ax_obj.set_ylim(LIMIT_Y_MIN, LIMIT_Y_MAX)
        ax_obj.set_aspect('equal')
        ax_obj.axis('off')
        ax_obj.set_title(label, fontsize=10, fontweight='bold', loc='left', color='black')

        # キャビン
        ax_obj.add_patch(patches.FancyBboxPatch((-CABIN_L, 0), CABIN_L-2, TRUCK_W_BODY, boxstyle="round,pad=0.2", fc='white', ec='black', lw=1.0))
        ax_obj.add_patch(patches.Rectangle((-CABIN_L + 2, 2), 8, TRUCK_W_BODY-4, fc=color_cab, ec='black'))
        ax_obj.plot([-CABIN_L+5, -CABIN_L+5], [TRUCK_W_BODY, TRUCK_W_BODY+3], color='black', lw=1.5)
        ax_obj.plot([-CABIN_L+5, -CABIN_L+5], [0, -3], color='black', lw=1.5)

        # 荷台
        ax_obj.add_patch(patches.Rectangle((0, 0), TRUCK_L, TRUCK_W_BODY, fc='#F5F5F5', ec='black', lw=1.0))
        ax_obj.plot([0, TRUCK_L], [TRUCK_W_BODY+3, TRUCK_W_BODY+3], color='silver', linestyle='--')
        ax_obj.plot([0, TRUCK_L], [-3, -3], color='silver', linestyle='--')

        # タイヤ
        tire_w = 12; tire_h = 6
        tire_x = [-CABIN_L + 15, TRUCK_L - 15] if truck_type == '4t' else [-CABIN_L + 15, TRUCK_L - 25, TRUCK_L - 12]
        for tx in tire_x:
            ax_obj.add_patch(patches.Rectangle((tx, TRUCK_W_BODY), tire_w, tire_h, fc='#333333', ec='black'))
            ax_obj.add_patch(patches.Rectangle((tx, -tire_h), tire_w, tire_h, fc='#333333', ec='black'))

        # パレット
        for i in range(max_p):
            c_idx = i % 2; r_idx = i // 2
            px = MARGIN + (r_idx * (PALLET_D + MARGIN))
            py = (TRUCK_W_BODY / 2) - PALLET_W - (MARGIN/2) if c_idx == 0 else (TRUCK_W_BODY / 2) + (MARGIN/2)
            
            ax_obj.add_patch(patches.Rectangle((px, py), PALLET_W, PALLET_D, fill=False, ec='silver', linestyle=':'))
            if i < current_p:
                color = '#90EE90' if truck_type == '10t' else '#87CEEB'
                ax_obj.add_patch(patches.Rectangle((px, py), PALLET_W, PALLET_D, fc=color, ec='black', alpha=0.8))
                ax_obj.text(px + PALLET_W/2, py + PALLET_D/2, f"P{i+1}", ha='center', va='center', fontsize=6, fontweight='bold', color='black')

    draw_truck_h(ax[0], '4t', 10, num_pallets)
    draw_truck_h(ax[1], '10t', 16, num_pallets)
    plt.tight_layout()
    return fig

# --- パレット詳細図描画 ---
def draw_pallet_figure(PW, PD, PH, p_items, figsize=(18, 5)):
    fig, ax = plt.subplots(1, 3, figsize=figsize)
    fig.patch.set_facecolor('white')
    
    # 共通設定
    for a in ax: a.set_facecolor('white')

    # 1. 上面図
    ax[0].set_aspect('equal')
    ax[0].add_patch(patches.Rectangle((0,0), PW, PD, fill=False, lw=2))
    sorted_items = sorted(p_items, key=lambda x: x.get('z', 0))
    for b in sorted_items:
        ax[0].add_patch(patches.Rectangle((b['x'], b['y']), b['w'], b['d'], facecolor=b['col'], edgecolor='black', alpha=0.7))
        txt = f"{b['name']}\n{b['ly']}段"
        if b.get('child'): txt += f"\n(上:{b['child']['name']})"
        ax[0].text(b['x'] + b['w']/2, b['y'] + b['d']/2, txt, ha='center', va='center', fontsize=8, color='black')
    ax[0].set_xlim(-50, PW+50); ax[0].set_ylim(-50, PD+50); ax[0].invert_yaxis()
    ax[0].set_title("① 上面図", color='black')
    
    # 2. 正面図
    ax[1].add_patch(patches.Rectangle((0,0), PW, PH, fill=False, lw=2))
    for b in p_items:
        z_base = b.get('z', 0)
        for ly in range(b['ly']):
            y_pos = z_base + ly * b['h']
            ax[1].add_patch(patches.Rectangle((b['x'], y_pos), b['w'], b['h'], facecolor=b['col'], edgecolor='black', alpha=0.5))
        ax[1].text(b['x'] + b['w']/2, z_base + b['h_total']/2, b['name'], ha='center', va='center', fontsize=8, color='black')
        if b.get('child'):
            c_blk = b['child']; c_base = z_base + b['h_total']
            for ly in range(c_blk['ly']):
                y_pos = c_base + ly * c_blk['h']
                ax[1].add_patch(patches.Rectangle((b['x'], y_pos), c_blk['w'], c_blk['h'], facecolor=c_blk['col'], edgecolor='black', alpha=0.5))
    ax[1].set_xlim(-50, PW+50); ax[1].set_ylim(0, PH+100)
    ax[1].set_title("② 正面図", color='black')

    # 3. 側面図
    ax[2].add_patch(patches.Rectangle((0,0), PD, PH, fill=False, lw=2))
    for b in p_items:
        z_base = b.get('z', 0)
        for ly in range(b['ly']):
            y_pos = z_base + ly * b['h']
            ax[2].add_patch(patches.Rectangle((b['y'], y_pos), b['d'], b['h'], facecolor=b['col'], edgecolor='black', alpha=0.5))
        ax[2].text(b['y'] + b['d']/2, z_base + b['h_total']/2, b['name'], ha='center', va='center', fontsize=8, color='black')
        if b.get('child'):
            c_blk = b['child']; c_base = z_base + b['h_total']
            for ly in range(c_blk['ly']):
                y_pos = c_base + ly * c_blk['h']
                ax[2].add_patch(patches.Rectangle((b['y'], y_pos), c_blk['w'], c_blk['h'], facecolor=c_blk['col'], edgecolor='black', alpha=0.5))
    ax[2].set_xlim(-50, PD+50); ax[2].set_ylim(0, PH+100)
    ax[2].set_title("③ 側面図", color='black')
    
    plt.tight_layout()
    return fig

# --- PDF生成 ---
def create_pdf(current_pallets, current_params, truck_img_bytes, input_products):
    buffer = io.BytesIO()
    if os.path.exists('ipaexg.ttf'):
        pdfmetrics.registerFont(TTFont('IPAexGothic', 'ipaexg.ttf'))
        font_name = "IPAexGothic"
    else:
        font_name = "Helvetica"

    c = canvas.Canvas(buffer, pagesize=A4)
    w_a4, h_a4 = A4

    # タイトル
    c.setFont(font_name, 20)
    c.drawString(40, h_a4 - 50, "パレット積載シミュレーション報告書")

    # トラック画像
    disp_h = 0
    if truck_img_bytes:
        truck_img_bytes.seek(0)
        img = ImageReader(truck_img_bytes)
        iw, ih = img.getSize()
        aspect = ih / float(iw)
        disp_w = 180
        disp_h = disp_w * aspect
        c.drawImage(img, w_a4 - disp_w - 20, h_a4 - 50 - disp_h - 10, width=disp_w, height=disp_h, preserveAspectRatio=True)

    # サマリー
    c.setFont(font_name, 12)
    total_p = len(current_pallets)
    truck_4t = total_p / 10.0
    truck_10t = total_p / 16.0

    text_y = h_a4 - 90
    c.drawString(40, text_y, f"必要パレット総数: {total_p} 枚")
    text_y -= 20
    c.drawString(40, text_y, f"  (目安: 4t車 {truck_4t:.1f}台 / 10t車 {truck_10t:.1f}台)")
    text_y -= 25
    c.drawString(40, text_y, f"パレット: {current_params['PW']}x{current_params['PD']}x{current_params['PH']}mm")
    text_y -= 15
    c.drawString(40, text_y, f"Max {current_params['MAX_W']}kg / 許容: {current_params['OH']}mm")

    # 入力商品情報の印字
    text_y -= 40
    c.drawString(40, text_y, "■ 入力商品情報")
    text_y -= 15
    c.setFont(font_name, 10)
    for p in input_products:
        if p['n'] > 0:
            txt = f"{p['name']}: {p['w']}x{p['d']}x{p['h']}mm, {p['g']}kg, {p['n']}個"
            c.drawString(50, text_y, txt)
            text_y -= 12

    # 詳細図配置
    bottom_of_truck = h_a4 - 50 - disp_h - 10
    start_y_p1 = min(text_y - 40, bottom_of_truck - 30)
    y = start_y_p1
    
    # ページ下端チェック用
    margin_bottom = 50

    PW = current_params['PW']; PD = current_params['PD']; PH = current_params['PH']

    for i, p_items in enumerate(current_pallets):
        # 簡易的な改ページ判定
        img_h_pdf = 150
        req_h = 15 + 15 + img_h_pdf + 20 
        
        if y - req_h < margin_bottom:
            c.showPage()
            c.setFont(font_name, 12)
            y = h_a4 - 50

        p_weight = sum([b['g'] + (b['child']['g'] if b['child'] else 0) for b in p_items])
        cnt = {}
        for b in p_items:
            cnt[b['name']] = cnt.get(b['name'], 0) + b['ly']
            if b.get('child'): cnt[b['child']['name']] = cnt.get(b['child']['name'], 0) + b['child']['ly']
        d_str = ", ".join([f"{k}:{v}個" for k,v in cnt.items()])

        c.setFont(font_name, 12)
        c.drawString(40, y, f"■ パレット {i+1}  (重量: {p_weight}kg)")
        
        c.setFont(font_name, 9)
        c.drawString(240, y, f"内訳: {d_str}")

        fig = draw_pallet_figure(PW, PD, PH, p_items, figsize=(12, 3.5))
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format='png', bbox_inches='tight')
        img_buf.seek(0); plt.close(fig)
        img = ImageReader(img_buf)

        c.drawImage(img, 40, y - 10 - img_h_pdf, width=520, height=img_h_pdf, preserveAspectRatio=True)
        y -= (15 + img_h_pdf + 20)

    c.save()
    buffer.seek(0)
    return buffer

# --------------------------------
# メイン UI (ラボ版レイアウトの再現)
# --------------------------------

st.title("パレット積載シミュレーター")

# デフォルト値
defaults = [
    (320, 300, 280, 6, 35),
    (340, 300, 250, 5, 32),
    (300, 340, 330, 8, 53),
    (250, 280, 220, 3, 23),
    (400, 350, 250, 6, 30)
]

# Session State初期化
if 'products' not in st.session_state:
    st.session_state.products = []
    for i in range(5):
        st.session_state.products.append({
            'w': defaults[i][0], 'd': defaults[i][1], 'h': defaults[i][2],
            'g': defaults[i][3], 'n': defaults[i][4]
        })

# クリアボタンのコールバック
def clear_row(idx):
    st.session_state.products[idx] = {'w':0, 'd':0, 'h':0, 'g':0, 'n':0}

# --- 1. パレット設定 (横一列) ---
st.markdown("##### 📦 パレット設定 (mm)")
c_pw, c_pd, c_ph, c_pm, c_oh = st.columns(5)
pw_val = c_pw.number_input("幅", value=1100, step=10)
pd_val = c_pd.number_input("奥行", value=1100, step=10)
ph_val = c_ph.number_input("高さ", value=1700, step=10)
pm_val = c_pm.number_input("Max重量(kg)", value=1000, step=10)
oh_val = c_oh.number_input("重ね積み許容(mm)", value=30, step=5)

st.markdown("---")

# --- 2. 商品入力 (ラボ版と同じ「行」構成) ---
st.markdown("##### 商品情報入力")
colors = ['#ff9999', '#99ccff', '#99ff99', '#ffff99', '#cc99ff']
products_data = []

# 【修正箇所】ヘッダー行を追加して、どの列が何の値かわかるようにしました
# レイアウト比率は下の入力欄と合わせています
cols_head = st.columns([0.6, 1, 1, 1, 1, 1, 0.7])
cols_head[0].markdown("") # 商品名用スペース（空）
cols_head[1].markdown("**幅(mm)**")
cols_head[2].markdown("**奥行(mm)**")
cols_head[3].markdown("**高さ(mm)**")
cols_head[4].markdown("**重量(kg)**")
cols_head[5].markdown("**数量(個)**")
cols_head[6].markdown("") # クリアボタン用スペース（空）

# 各行をループで作成 (横並び配置)
for i in range(5):
    # 行のレイアウト: [商品名] [幅] [奥] [高] [重] [数] [クリアボタン]
    # 比率調整: ラベルは少し狭く、数値入力は均等、ボタンは狭く
    cols = st.columns([0.6, 1, 1, 1, 1, 1, 0.7])
    
    with cols[0]:
        st.markdown(f"**商品{i+1}**")
        st.markdown(f'<div style="background-color:{colors[i]}; height:5px; width:100%;"></div>', unsafe_allow_html=True)

    # 入力フィールド (ラベルは非表示にして、上のヘッダーで見せる)
    
    # 幅
    w = cols[1].number_input("幅", value=st.session_state.products[i]['w'], key=f"w_{i}", label_visibility="collapsed")
    st.session_state.products[i]['w'] = w 
    
    # 奥行
    d = cols[2].number_input("奥", value=st.session_state.products[i]['d'], key=f"d_{i}", label_visibility="collapsed")
    st.session_state.products[i]['d'] = d
    
    # 高さ
    h = cols[3].number_input("高", value=st.session_state.products[i]['h'], key=f"h_{i}", label_visibility="collapsed")
    st.session_state.products[i]['h'] = h
    
    # 重量
    g = cols[4].number_input("重", value=st.session_state.products[i]['g'], key=f"g_{i}", label_visibility="collapsed")
    st.session_state.products[i]['g'] = g
    
    # 数量
    n = cols[5].number_input("数", value=st.session_state.products[i]['n'], key=f"n_{i}", label_visibility="collapsed")
    st.session_state.products[i]['n'] = n
    
    # クリアボタン
    with cols[6]:
        st.button("クリア", key=f"clr_{i}", on_click=clear_row, args=(i,))

    products_data.append({
        'name': f"商品{i+1}", 'w': w, 'd': d, 'h': h, 'g': g, 'n': n, 
        'col': colors[i], 'id': i
    })

st.markdown("---")

# --- 計算実行ボタン ---
if st.button("計算実行", type="primary", use_container_width=True):
    # パラメータ取得
    PW, PD, PH = pw_val, pd_val, ph_val
    MAX_W, OH = pm_val, oh_val
    
    items = []
    for p in products_data:
        if p['n'] > 0 and p['w'] > 0:
            items.append({
                'name': p['name'], 'w': p['w'], 'd': p['d'], 'h': p['h'], 
                'g': p['g'], 'n': p['n'], 'col': p['col'], 'p_id': p['id']
            })

    if not items:
        st.error("商品データが入力されていません。")
    else:
        # --- 計算ロジック ---
        blocks = []
        for p in items:
            layers = max(1, int(PH // p['h']))
            full = int(p['n'] // layers)
            rem = int(p['n'] % layers)
            g_t, h_t = layers * p['g'], layers * p['h']
            for _ in range(full): 
                blocks.append({'name':p['name'], 'w':p['w'], 'd':p['d'], 'h':p['h'], 'ly':layers, 'g':g_t, 'col':p['col'], 'h_total':h_t, 'child':None, 'z':0, 'p_id':p['p_id']})
            if rem > 0: 
                blocks.append({'name':p['name'], 'w':p['w'], 'd':p['d'], 'h':p['h'], 'ly':rem, 'g':rem*p['g'], 'col':p['col'], 'h_total':rem*p['h'], 'child':None, 'z':0, 'p_id':p['p_id']})

        blocks.sort(key=lambda x: (x['p_id'], -x['w']*x['d'], -x['h_total']))
        merged_indices = set()
        for i in range(len(blocks)):
            if i in merged_indices: continue
            base = blocks[i]
            limit_w = base['w'] + (OH * 2); limit_d = base['d'] + (OH * 2)
            for j in range(i + 1, len(blocks)):
                if j in merged_indices: continue
                top = blocks[j]
                if top['h_total'] > base['h_total']: continue
                if (base['h_total'] + top['h_total'] > PH): continue
                if ((limit_w >= top['w'] and limit_d >= top['d']) or (limit_w >= top['d'] and limit_d >= top['w'])):
                    if not (limit_w >= top['w'] and limit_d >= top['d']): top['w'], top['d'] = top['d'], top['w']
                    base['child'] = top; merged_indices.add(j); break

        active_blocks = [b for k, b in enumerate(blocks) if k not in merged_indices]
        pallet_states = []
        for blk in active_blocks:
            w_total = blk['g'] + (blk['child']['g'] if blk['child'] else 0)
            placed = False
            for p_state in pallet_states:
                if p_state['cur_g'] + w_total > MAX_W: continue
                fit = False
                temp_cx, temp_cy, temp_rh = p_state['cx'], p_state['cy'], p_state['rh']
                if temp_cx + blk['w'] <= PW and temp_cy + blk['d'] <= PD: fit = True
                elif temp_cy + temp_rh + blk['d'] <= PD:
                    temp_cx = 0; temp_cy += temp_rh; temp_rh = 0
                    if temp_cx + blk['w'] <= PW and temp_cy + blk['d'] <= PD: fit = True
                if fit:
                    blk['x'] = temp_cx; blk['y'] = temp_cy; blk['z'] = 0
                    p_state['items'].append(blk); p_state['cur_g'] += w_total
                    p_state['cx'] = temp_cx + blk['w']; p_state['cy'] = temp_cy; p_state['rh'] = max(temp_rh, blk['d'])
                    placed = True; break
            if not placed:
                new_state = {'items': [blk], 'cur_g': w_total, 'cx': blk['w'], 'cy': 0, 'rh': blk['d']}
                blk['x'] = 0; blk['y'] = 0; blk['z'] = 0; pallet_states.append(new_state)

        # 保存
        st.session_state.results = [ps['items'] for ps in pallet_states]
        st.session_state.params = {'PW':PW, 'PD':PD, 'PH':PH, 'MAX_W':MAX_W, 'OH':OH}
        st.session_state.input_products = items # PDF用
        st.session_state.calculated = True

# --- 結果表示 ---
if st.session_state.get('calculated', False):
    results = st.session_state.results
    params = st.session_state.params
    total_p = len(results)
    
    st.markdown("### 📊 計算結果")
    
    # トラック図（白背景）
    fig_truck = create_horizontal_trucks_figure(total_p)
    img_buf = io.BytesIO()
    fig_truck.savefig(img_buf, format='png', bbox_inches='tight', dpi=300, facecolor='white')
    img_buf.seek(0)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("必要パレット数", f"{total_p} 枚")
        st.info(f"🚚 4t車: {total_p/10.0:.1f} 台 / 10t車: {total_p/16.0:.1f} 台")
        
        pdf_file = create_pdf(results, params, img_buf, st.session_state.input_products)
        st.download_button(
            label="📄 PDFレポートをダウンロード",
            data=pdf_file,
            file_name="pallet_report.pdf",
            mime="application/pdf",
            type="primary"
        )
    with col2:
        st.pyplot(fig_truck)

    st.markdown("---")
    st.subheader("詳細: パレット内訳")

    for i, p_items in enumerate(results):
        with st.expander(f"パレット {i+1} (クリックで展開)", expanded=(i==0)):
            p_weight = sum([b['g'] + (b['child']['g'] if b['child'] else 0) for b in p_items])
            cnt = {}
            for b in p_items:
                cnt[b['name']] = cnt.get(b['name'], 0) + b['ly']
                if b['child']: cnt[b['child']['name']] = cnt.get(b['child']['name'], 0) + b['child']['ly']
            d_str = ", ".join([f"{k}:{v}個" for k,v in cnt.items()])
            
            st.markdown(f"**重量: {p_weight}kg** | 内訳: {d_str}")
            
            fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], p_items)
            st.pyplot(fig)
