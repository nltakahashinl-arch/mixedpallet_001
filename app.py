import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
import os
import urllib.request
import zipfile
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- ページ設定 (ワイド表示) ---
st.set_page_config(layout="wide", page_title="パレット積載シミュレーター")

# ログアウトボタン
if st.sidebar.button("ログアウト"):
    st.session_state.authenticated = False
    st.rerun()

# --- フォント準備 ---
@st.cache_resource
def setup_font():
    font_path = "ipaexg.ttf"
    if not os.path.exists(font_path):
        url = "https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.zip"
        zip_name = "ipaexg00401.zip"
        try:
            urllib.request.urlretrieve(url, zip_name)
            with zipfile.ZipFile(zip_name, 'r') as z:
                z.extractall(".")
            extracted_path = "ipaexg00401/ipaexg.ttf"
            if os.path.exists(extracted_path):
                os.replace(extracted_path, font_path)
        except Exception:
            pass
    return font_path

font_file = setup_font()
if font_file:
    import matplotlib.font_manager as fm
    fm.fontManager.addfont(font_file)
    plt.rc('font', family='IPAexGothic')

# --- トラック描画関数 ---
def create_horizontal_trucks_figure(num_pallets):
    fig, ax = plt.subplots(2, 1, figsize=(6, 3))
    fig.patch.set_facecolor('white')

    SCALE = 1/100
    PALLET_W = 1100 * SCALE
    PALLET_D = 1100 * SCALE
    TRUCK_W_BODY = 2400 * SCALE
    MAX_L_10T = 9600 * SCALE
    CABIN_L = 1500 * SCALE
    MARGIN = 50 * SCALE

    LIMIT_X_MIN = -CABIN_L - 10
    LIMIT_X_MAX = MAX_L_10T + 20
    LIMIT_Y_MIN = -15
    LIMIT_Y_MAX = TRUCK_W_BODY + 20

    def draw_truck_h(ax_obj, truck_type, max_p, current_p):
        ax_obj.set_facecolor('white')
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

        ax_obj.add_patch(patches.FancyBboxPatch((-CABIN_L, 0), CABIN_L-2, TRUCK_W_BODY, boxstyle="round,pad=0.2", fc='white', ec='black', lw=1.0))
        ax_obj.add_patch(patches.Rectangle((-CABIN_L + 2, 2), 8, TRUCK_W_BODY-4, fc=color_cab, ec='black'))
        ax_obj.plot([-CABIN_L+5, -CABIN_L+5], [TRUCK_W_BODY, TRUCK_W_BODY+3], color='black', lw=1.5)
        ax_obj.plot([-CABIN_L+5, -CABIN_L+5], [0, -3], color='black', lw=1.5)

        ax_obj.add_patch(patches.Rectangle((0, 0), TRUCK_L, TRUCK_W_BODY, fc='#F5F5F5', ec='black', lw=1.0))
        ax_obj.plot([0, TRUCK_L], [TRUCK_W_BODY+3, TRUCK_W_BODY+3], color='silver', linestyle='--')
        ax_obj.plot([0, TRUCK_L], [-3, -3], color='silver', linestyle='--')

        tire_w = 12; tire_h = 6
        tire_x = [-CABIN_L + 15, TRUCK_L - 15] if truck_type == '4t' else [-CABIN_L + 15, TRUCK_L - 25, TRUCK_L - 12]
        for tx in tire_x:
            ax_obj.add_patch(patches.Rectangle((tx, TRUCK_W_BODY), tire_w, tire_h, fc='#333333', ec='black'))
            ax_obj.add_patch(patches.Rectangle((tx, -tire_h), tire_w, tire_h, fc='#333333', ec='black'))

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

# --- パレット詳細図描画 (5面図) ---
def draw_pallet_figure(PW, PD, PH, p_items, figsize=(18, 8)):
    fig = plt.figure(figsize=figsize)
    fig.patch.set_facecolor('white')
    
    gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 1, 1], height_ratios=[1, 1])

    # 1. 上面図
    ax_top = fig.add_subplot(gs[:, 0])
    ax_top.set_facecolor('white')
    ax_top.set_aspect('equal')
    ax_top.add_patch(patches.Rectangle((0,0), PW, PD, fill=False, lw=2))
    
    sorted_items_z = sorted(p_items, key=lambda x: x.get('z', 0))
    for b in sorted_items_z:
        ax_top.add_patch(patches.Rectangle((b['x'], b['y']), b['w'], b['d'], facecolor=b['col'], edgecolor='black', alpha=0.9))
        txt = f"{b['disp_name']}\n{b['ly']}段" # 表示名を使用
        if b.get('child'): txt += f"\n(上:{b['child']['disp_name']})"
        ax_top.text(b['x'] + b['w']/2, b['y'] + b['d']/2, txt, ha='center', va='center', fontsize=8, color='black')
    ax_top.set_xlim(-50, PW+50); ax_top.set_ylim(-50, PD+50); ax_top.invert_yaxis()
    ax_top.set_title("① 上面図 (Top)", color='black', fontsize=12, fontweight='bold')

    # 共通描画関数
    def plot_side_view(ax, axis_h, axis_v, items, sort_key, reverse_sort, title, label_func):
        ax.set_facecolor('white')
        limit_h = PW if axis_h == 'x' else PD
        ax.add_patch(patches.Rectangle((0,0), limit_h, PH, fill=False, lw=2))
        
        sorted_items = sorted(items, key=lambda x: x[sort_key], reverse=reverse_sort)

        # 奥行き判定用の最前面座標
        if items:
            min_depth = min([b[sort_key] for b in items])
            max_depth = max([b[sort_key] for b in items])
            front_val = max_depth if reverse_sort else min_depth
        else:
            front_val = 0

        for b in sorted_items:
            z_base = b.get('z', 0)
            h_pos = b[axis_h]
            w_size = b['w'] if axis_h == 'x' else b['d']
            
            # 手前判定 (10mmの誤差許容)
            depth_pos = b[sort_key]
            is_front = abs(depth_pos - front_val) <= 10
            
            # 手前はくっきり、奥は薄く
            alpha_val = 1.0 if is_front else 0.3
            lw_val = 1.5 if is_front else 0.5

            for ly in range(b['ly']):
                y_pos = z_base + ly * b['h']
                ax.add_patch(patches.Rectangle((h_pos, y_pos), w_size, b['h'], 
                    facecolor=b['col'], edgecolor='black', alpha=alpha_val, lw=lw_val))
            
            center_h = h_pos + w_size/2
            center_v = z_base + b['h_total']/2
            ax.text(center_h, center_v, label_func(b), ha='center', va='center', fontsize=7, color='black')

            if b.get('child'):
                c = b['child']
                c_h_pos = b[axis_h]
                c_w_size = c['w'] if axis_h == 'x' else c['d']
                c_base = z_base + b['h_total']
                for ly in range(c['ly']):
                    y_pos = c_base + ly * c['h']
                    ax.add_patch(patches.Rectangle((c_h_pos, y_pos), c_w_size, c['h'], 
                        facecolor=c['col'], edgecolor='black', alpha=alpha_val, lw=lw_val))

        ax.set_xlim(-50, limit_h+50); ax.set_ylim(0, PH+100)
        ax.set_title(title, color='black', fontsize=10, fontweight='bold')

    lbl = lambda b: b['disp_name']

    ax_front = fig.add_subplot(gs[0, 1])
    plot_side_view(ax_front, 'x', 'z', p_items, 'y', True, "② 正面図 (Front)", lbl)

    ax_back = fig.add_subplot(gs[0, 2])
    plot_side_view(ax_back, 'x', 'z', p_items, 'y', False, "③ 背面図 (Back)", lbl)

    ax_left = fig.add_subplot(gs[1, 1])
    plot_side_view(ax_left, 'y', 'z', p_items, 'x', True, "④ 左側面図 (Left)", lbl)

    ax_right = fig.add_subplot(gs[1, 2])
    plot_side_view(ax_right, 'y', 'z', p_items, 'x', False, "⑤ 右側面図 (Right)", lbl)

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

    c.setFont(font_name, 20)
    c.drawString(40, h_a4 - 50, "パレット積載シミュレーション報告書")

    disp_h = 0
    if truck_img_bytes:
        truck_img_bytes.seek(0)
        img = ImageReader(truck_img_bytes)
        iw, ih = img.getSize()
        aspect = ih / float(iw)
        disp_w = 180
        disp_h = disp_w * aspect
        c.drawImage(img, w_a4 - disp_w - 20, h_a4 - 50 - disp_h - 10, width=disp_w, height=disp_h, preserveAspectRatio=True)

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
    c.drawString(40, text_y, f"Max {current_params['MAX_W']}kg /許容: {current_params['OH']}mm")

    text_y -= 40
    c.drawString(40, text_y, "■ 入力商品情報")
    text_y -= 15
    c.setFont(font_name, 10)
    for p in input_products:
        if p['n'] > 0:
            txt = f"{p['name']}: {p['w']}x{p['d']}x{p['h']}mm, {p['g']}kg, {p['n']}個"
            c.drawString(50, text_y, txt)
            text_y -= 12

    bottom_of_truck = h_a4 - 50 - disp_h - 10
    start_y_p1 = min(text_y - 40, bottom_of_truck - 30)
    y = start_y_p1
    
    margin_bottom = 50

    PW = current_params['PW']; PD = current_params['PD']; PH = current_params['PH']

    for i, p_items in enumerate(current_pallets):
        img_h_pdf = 200
        req_h = 15 + 15 + img_h_pdf + 20 
        
        if y - req_h < margin_bottom:
            c.showPage()
            c.setFont(font_name, 12)
            y = h_a4 - 50

        p_weight = sum([b['g'] + (b['child']['g'] if b['child'] else 0) for b in p_items])
        cnt = {}
        for b in p_items:
            cnt[b['disp_name']] = cnt.get(b['disp_name'], 0) + b['ly']
            if b.get('child'): cnt[b['child']['disp_name']] = cnt.get(b['child']['disp_name'], 0) + b['child']['ly']
        d_str = ", ".join([f"{k}:{v}個" for k,v in cnt.items()])

        c.setFont(font_name, 12)
        c.drawString(40, y, f"■ パレット {i+1}  (重量: {p_weight}kg)")
        
        c.setFont(font_name, 9)
        c.drawString(240, y, f"内訳: {d_str}")

        fig = draw_pallet_figure(PW, PD, PH, p_items, figsize=(12, 6))
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
# メイン UI
# --------------------------------

st.title("📦 パレット積載シミュレーター")

# --- 1. パレット設定 ---
with st.expander("パレット設定", expanded=True):
    c_pw, c_pd, c_ph, c_pm, c_oh = st.columns(5)
    pw_val = c_pw.number_input("幅 (mm)", value=1100, step=10)
    pd_val = c_pd.number_input("奥行 (mm)", value=1100, step=10)
    ph_val = c_ph.number_input("高さ (mm)", value=1700, step=10)
    pm_val = c_pm.number_input("Max重量(kg)", value=1000, step=10)
    oh_val = c_oh.number_input("重ね積み許容(mm)", value=30, step=5)

st.markdown("---")

# --- 2. 商品入力 (Excel貼り付け対応) ---
st.subheader("商品情報入力")
st.info("💡 Excelからコピーして、表の左上のセルを選択し `Ctrl+V` で貼り付けられます。「優先度」が高いほど先に（下に）積まれます。")

if 'editor_key' not in st.session_state:
    st.session_state.editor_key = 0

# 空データ生成 (列を追加)
def get_empty_data():
    df = pd.DataFrame({
        "商品名": pd.Series([""] * 15, dtype="str"),
        "幅(mm)": pd.Series([0]*15, dtype="int"),
        "奥行(mm)": pd.Series([0]*15, dtype="int"),
        "高さ(mm)": pd.Series([0]*15, dtype="int"),
        "重量(kg)": pd.Series([0.0]*15, dtype="float"),
        "数量": pd.Series([0]*15, dtype="int"),
        "優先度": pd.Series([1]*15, dtype="int"), # デフォルト優先度1
        "配置向き": pd.Series(["自動"]*15, dtype="str") # デフォルト自動
    })
    return df

if 'df_products' not in st.session_state:
    st.session_state.df_products = get_empty_data()

col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    if st.button("🗑️ 全てクリア (入力を空にする)", use_container_width=True):
        del st.session_state['df_products']
        st.session_state.df_products = get_empty_data()
        st.session_state.editor_key += 1
        st.rerun()

st.session_state.df_products["商品名"] = st.session_state.df_products["商品名"].astype(str)

# データエディタ (列構成を更新)
column_order = ["商品名", "幅(mm)", "奥行(mm)", "高さ(mm)", "重量(kg)", "数量", "優先度", "配置向き"]

edited_df = st.data_editor(
    st.session_state.df_products,
    key=f"data_editor_{st.session_state.editor_key}",
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_order=column_order,
    column_config={
        "商品名": st.column_config.TextColumn("商品名", width="large", required=True, default="", validate="^.*$"),
        "幅(mm)": st.column_config.NumberColumn("幅(mm)", min_value=0, format="%d"),
        "奥行(mm)": st.column_config.NumberColumn("奥行(mm)", min_value=0, format="%d"),
        "高さ(mm)": st.column_config.NumberColumn("高さ(mm)", min_value=0, format="%d"),
        "重量(kg)": st.column_config.NumberColumn("重量(kg)", min_value=0.0, format="%.1f"),
        "数量": st.column_config.NumberColumn("数量", min_value=0, format="%d"),
        "優先度": st.column_config.NumberColumn("優先度(大=下)", min_value=1, max_value=100, step=1, help="数字が大きい商品を先に（下に）配置します"),
        "配置向き": st.column_config.SelectboxColumn("配置向き", options=["自動", "横固定", "縦固定"], required=True, default="自動", help="回転を強制したい場合に指定してください"),
    }
)

st.markdown("---")

# --- 計算実行ボタン ---
if st.button("計算実行", type="primary", use_container_width=True):
    PW, PD, PH = pw_val, pd_val, ph_val
    MAX_W, OH = pm_val, oh_val
    
    items = []
    colors = ['#ff9999', '#99ccff', '#99ff99', '#ffff99', '#cc99ff', '#ffa07a', '#87cefa', '#f0e68c', '#dda0dd', '#90ee90'] 
    
    for idx, row in edited_df.iterrows():
        try:
            name = str(row["商品名"])
            if not name or name == "nan" or not name.strip(): continue
                
            w = int(row["幅(mm)"])
            d = int(row["奥行(mm)"])
            h = int(row["高さ(mm)"])
            g = float(row["重量(kg)"])
            n = int(row["数量"])
            prio = int(row["優先度"]) if "優先度" in row else 1
            orient = str(row["配置向き"]) if "配置向き" in row else "自動"
            
            if n <= 0 or w <= 0: continue

            # --- 配置向きの事前チェック ---
            # 縦固定なら最初からWとDを入れ替えておく
            # 横固定ならそのまま
            # 自動ならそのまま (あとでロジックで試行)
            force_w, force_d = w, d
            if orient == "縦固定":
                force_w, force_d = d, w
            
            # 基本的なサイズチェック (固定向きで入るか？)
            # 自動の場合はどちらかで入ればOK
            if orient == "自動":
                can_fit = (w <= PW and d <= PD) or (d <= PW and w <= PD)
            else:
                can_fit = (force_w <= PW and force_d <= PD)

            can_fit_h = h <= PH
            can_fit_weight = g <= MAX_W

            if not can_fit:
                st.error(f"❌ {name} はサイズオーバーです（向き: {orient}）。")
                continue
            elif not can_fit_h:
                st.error(f"❌ {name} は高さオーバーです。")
                continue
            elif not can_fit_weight:
                st.error(f"❌ {name} は単体重量オーバーです。")
                continue
            
            col = colors[idx % len(colors)]
            
            # 図に表示する名前 (No.を付与)
            disp_name = f"({idx+1}) {name}"

            items.append({
                'name': name, 'disp_name': disp_name, 
                'w': force_w, 'd': force_d, 'h': h, 
                'g': g, 'n': n, 'col': col, 'id': idx,
                'prio': prio, 'orient': orient,
                'orig_w': w, 'orig_d': d # 自動回転用に元のサイズも保持
            })

        except ValueError:
            continue

    if not items:
        st.error("計算可能な商品データがありません。")
    else:
        # --- 計算ロジック (優先度 & 指定向き対応) ---
        blocks = []
        for p in items:
            layers = max(1, int(PH // p['h']))
            full = int(p['n'] // layers)
            rem = int(p['n'] % layers)
            g_t, h_t = layers * p['g'], layers * p['h']
            for _ in range(full): 
                blocks.append({
                    'name':p['name'], 'disp_name':p['disp_name'], 
                    'w':p['w'], 'd':p['d'], 'h':p['h'], 'ly':layers, 'g':g_t, 'col':p['col'], 
                    'h_total':h_t, 'child':None, 'z':0, 'p_id':p['id'],
                    'prio': p['prio'], 'orient': p['orient'], 'orig_w': p['orig_w'], 'orig_d': p['orig_d']
                })
            if rem > 0: 
                blocks.append({
                    'name':p['name'], 'disp_name':p['disp_name'],
                    'w':p['w'], 'd':p['d'], 'h':p['h'], 'ly':rem, 'g':rem*p['g'], 'col':p['col'], 
                    'h_total':rem*p['h'], 'child':None, 'z':0, 'p_id':p['id'],
                    'prio': p['prio'], 'orient': p['orient'], 'orig_w': p['orig_w'], 'orig_d': p['orig_d']
                })

        # ソート順: 優先度(降順) > 面積(降順) > 高さ(降順)
        # 優先度が高いものが先頭に来る
        blocks.sort(key=lambda x: (-x['prio'], -x['w']*x['d'], -x['h_total']))
        
        # 重ね積み（子ブロック）の処理
        merged_indices = set()
        for i in range(len(blocks)):
            if i in merged_indices: continue
            base = blocks[i]
            limit_w = base['w'] + (OH * 2); limit_d = base['d'] + (OH * 2)
            
            # 同じ優先度、または低い優先度のものしか上に積めない（簡易ルール）
            for j in range(i + 1, len(blocks)):
                if j in merged_indices: continue
                top = blocks[j]
                if top['h_total'] > base['h_total']: continue
                if (base['h_total'] + top['h_total'] > PH): continue
                
                # サイズチェック (回転指示を考慮)
                # baseは既に固定されている。topも固定済みだが、自動なら回転チャンスあり
                
                can_stack = False
                final_top_w, final_top_d = top['w'], top['d']

                # 現状で乗るか
                if (limit_w >= top['w'] and limit_d >= top['d']) or (limit_w >= top['d'] and limit_d >= top['w']):
                     # 乗るなら向き決定
                     if not (limit_w >= top['w'] and limit_d >= top['d']):
                         # 90度回せば乗る
                         if top['orient'] == "横固定": pass # 回せないのでNG
                         elif top['orient'] == "縦固定": pass # 既に回ってるのでNG (ロジック上ここには来にくいが念のため)
                         else: 
                             final_top_w, final_top_d = top['d'], top['w']
                             can_stack = True
                     else:
                         can_stack = True
                
                # 自動の場合、まだチャンスがあるか？
                # (上でチェック済みだが、念のため元サイズからの回転も確認)
                if not can_stack and top['orient'] == "自動":
                     # w, dを入れ替えてチェック
                     rot_w, rot_d = top['d'], top['w']
                     if (limit_w >= rot_w and limit_d >= rot_d) or (limit_w >= rot_d and limit_d >= rot_w):
                         if limit_w >= rot_w and limit_d >= rot_d:
                             final_top_w, final_top_d = rot_w, rot_d
                             can_stack = True
                         else:
                             # さらに回す？いや同じこと。
                             final_top_w, final_top_d = rot_d, rot_w
                             can_stack = True

                if can_stack:
                    top['w'], top['d'] = final_top_w, final_top_d
                    base['child'] = top; merged_indices.add(j); break

        active_blocks = [b for k, b in enumerate(blocks) if k not in merged_indices]
        pallet_states = []
        
        for blk in active_blocks:
            w_total = blk['g'] + (blk['child']['g'] if blk['child'] else 0)
            placed = False
            
            for p_state in pallet_states:
                if p_state['cur_g'] + w_total > MAX_W: continue
                
                temp_cx, temp_cy, temp_rh = p_state['cx'], p_state['cy'], p_state['rh']
                
                # 配置候補の向きリスト作成
                try_orientations = []
                if blk['orient'] == "自動":
                    try_orientations = [(blk['w'], blk['d']), (blk['d'], blk['w'])]
                else:
                    # 固定の場合は今のサイズ一択
                    try_orientations = [(blk['w'], blk['d'])]

                best_fit = None
                
                # 既存列への追加トライ
                for tw, td in try_orientations:
                    # そのまま後ろにおけるか
                    if temp_cx + tw <= PW and temp_cy + td <= PD:
                        best_fit = ('current_row', tw, td)
                        break
                    # 改行して置けるか
                    elif temp_cy + temp_rh + td <= PD:
                        if tw <= PW:
                            best_fit = ('new_row', tw, td)
                            break
                
                if best_fit:
                    mode, fin_w, fin_d = best_fit
                    if mode == 'new_row':
                        temp_cx = 0; temp_cy += temp_rh; temp_rh = 0
                    
                    blk['w'], blk['d'] = fin_w, fin_d
                    blk['x'] = temp_cx; blk['y'] = temp_cy; blk['z'] = 0
                    p_state['items'].append(blk); p_state['cur_g'] += w_total
                    p_state['cx'] = temp_cx + fin_w; p_state['cy'] = temp_cy; p_state['rh'] = max(temp_rh, fin_d)
                    placed = True; break
            
            if not placed:
                # 新規パレット
                # 新規の場合も、自動なら「幅に合わせて最適な向き」で置く
                fin_w, fin_d = blk['w'], blk['d']
                if blk['orient'] == "自動":
                    # 幅1100に対して、300x400なら 400x300(横長)で置いたほうが列効率が良いかもしれない？
                    # 単純に「幅に収まる最大幅」をとるか、デフォルトのままにするか
                    # ここでは、もし幅からはみ出るなら回転、そうでなければデフォルト、とする
                    if blk['w'] > PW and blk['d'] <= PW:
                        fin_w, fin_d = blk['d'], blk['w']
                
                blk['w'], blk['d'] = fin_w, fin_d
                new_state = {'items': [blk], 'cur_g': w_total, 'cx': blk['w'], 'cy': 0, 'rh': blk['d']}
                blk['x'] = 0; blk['y'] = 0; blk['z'] = 0; pallet_states.append(new_state)

        st.session_state.results = [ps['items'] for ps in pallet_states]
        st.session_state.params = {'PW':PW, 'PD':PD, 'PH':PH, 'MAX_W':MAX_W, 'OH':OH}
        st.session_state.input_products = items
        st.session_state.calculated = True

# --- 結果表示 ---
if st.session_state.get('calculated', False):
    results = st.session_state.results
    params = st.session_state.params
    total_p = len(results)
    
    st.markdown("### 📊 計算結果")
    
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
        with st.expander(f"パレット {i+1}", expanded=True):
            p_weight = sum([b['g'] + (b['child']['g'] if b['child'] else 0) for b in p_items])
            cnt = {}
            for b in p_items:
                cnt[b['disp_name']] = cnt.get(b['disp_name'], 0) + b['ly']
                if b['child']: cnt[b['child']['disp_name']] = cnt.get(b['child']['disp_name'], 0) + b['child']['ly']
            d_str = ", ".join([f"{k}:{v}個" for k,v in cnt.items()])
            
            st.markdown(f"**重量: {p_weight}kg** | 内訳: {d_str}")
            
            fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], p_items)
            st.pyplot(fig)
