import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
import os
import urllib.request
import zipfile
import pandas as pd
import uuid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- ページ設定 (ワイド表示) ---
st.set_page_config(layout="wide", page_title="パレット積載シミュレーター (統合版)")

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

# --- ユーティリティ ---
def get_empty_data():
    df = pd.DataFrame({
        "商品名": pd.Series([""] * 10, dtype="str"),
        "幅(mm)": pd.Series([0]*10, dtype="int"),
        "奥行(mm)": pd.Series([0]*10, dtype="int"),
        "高さ(mm)": pd.Series([0]*10, dtype="int"),
        "重量(kg)": pd.Series([0.0]*10, dtype="float"),
        "数量": pd.Series([0]*10, dtype="int"),
        "優先度": pd.Series([1]*10, dtype="int"),
        "配置向き": pd.Series(["自動"]*10, dtype="str")
    })
    return df

# --- 描画関数 (5面図・詳細版・不透明化修正) ---
def draw_pallet_figure(PW, PD, PH, p_items, figsize=(18, 8)):
    fig = plt.figure(figsize=figsize)
    fig.patch.set_facecolor('white')
    
    gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 1, 1], height_ratios=[1, 1])

    # ① 上面図
    ax_top = fig.add_subplot(gs[:, 0])
    ax_top.set_facecolor('white')
    ax_top.set_aspect('equal')
    ax_top.add_patch(patches.Rectangle((0,0), PW, PD, fill=False, lw=2))
    
    # Z順（下にあるものを先に描く）
    sorted_items_z = sorted(p_items, key=lambda x: x.get('z', 0))
    for b in sorted_items_z:
        # alpha=1.0 (不透明) に変更
        ax_top.add_patch(patches.Rectangle((b['x'], b['y']), b['w'], b['d'], 
                                           facecolor=b['col'], edgecolor='black', alpha=1.0, linewidth=1))
        
        disp_id = b.get('sub_id', '')
        txt = f"{b['name']}\n#{disp_id}"
        ax_top.text(b['x'] + b['w']/2, b['y'] + b['d']/2, txt, ha='center', va='center', fontsize=8, color='black', clip_on=True)
        
    ax_top.set_xlim(-50, PW+50); ax_top.set_ylim(-50, PD+50); ax_top.invert_yaxis()
    ax_top.set_title("① 上面図 (Top)", color='black', fontsize=12, fontweight='bold')

    # 側面図描画用ヘルパー
    def plot_side_view(ax, axis_h, axis_v, items, sort_key, reverse_sort, title):
        ax.set_facecolor('white')
        limit_h = PW if axis_h == 'x' else PD
        ax.add_patch(patches.Rectangle((0,0), limit_h, PH, fill=False, lw=2))
        
        # 描画順序: 奥にあるものから先に描く (Painter's Algorithm)
        # reverse_sort=True (降順) の場合、値が大きい順。
        # 例: 正面図(Front)はY軸。手前がY=0なら、奥はY=Max。
        # 奥(Y大)から描画し、手前(Y小)を重ねることで正しい見た目になる。
        # なので reverse=True (降順) で正解。
        
        sorted_items = sorted(items, key=lambda x: x[sort_key], reverse=reverse_sort)
        
        for b in sorted_items:
            h_pos = b[axis_h]
            v_pos = b[axis_v]
            w_size = b['w'] if axis_h == 'x' else b['d']
            h_size = b['h']
            
            # alpha=1.0 (不透明) に変更
            ax.add_patch(patches.Rectangle((h_pos, v_pos), w_size, h_size, 
                                           facecolor=b['col'], edgecolor='black', alpha=1.0, linewidth=1))
            
            # 不透明なので、隠れずに見えている部分に文字が出るとは限らないが、
            # とりあえず中心に表示
            ax.text(h_pos + w_size/2, v_pos + h_size/2, f"{b['name']}", ha='center', va='center', fontsize=7, color='black', clip_on=True)

        ax.set_xlim(-50, limit_h+50); ax.set_ylim(0, PH+100)
        ax.set_title(title, color='black', fontsize=10, fontweight='bold')

    # 各側面図
    ax_front = fig.add_subplot(gs[0, 1])
    plot_side_view(ax_front, 'x', 'z', p_items, 'y', True, "② 正面図 (Front)")

    ax_back = fig.add_subplot(gs[0, 2])
    # 背面図: Y小(手前)から描いて、Y大(奥)を重ねる -> reverse=False (昇順)
    plot_side_view(ax_back, 'x', 'z', p_items, 'y', False, "③ 背面図 (Back)")

    ax_left = fig.add_subplot(gs[1, 1])
    # 左側面: X大(右)から描いて、X小(左)を重ねる -> reverse=True
    plot_side_view(ax_left, 'y', 'z', p_items, 'x', True, "④ 左側面図 (Left)")

    ax_right = fig.add_subplot(gs[1, 2])
    # 右側面: X小(左)から描いて、X大(右)を重ねる -> reverse=False
    plot_side_view(ax_right, 'y', 'z', p_items, 'x', False, "⑤ 右側面図 (Right)")

    plt.tight_layout()
    return fig

# --- PDF生成 (簡易版) ---
def create_pdf(current_pallets, params):
    buffer = io.BytesIO()
    font_name = "IPAexGothic" if os.path.exists('ipaexg.ttf') else "Helvetica"
    c = canvas.Canvas(buffer, pagesize=A4)
    w_a4, h_a4 = A4
    y = h_a4 - 50
    c.setFont(font_name, 16)
    c.drawString(40, y, "パレット積載シミュレーション報告書")
    y -= 30
    c.setFont(font_name, 10)
    
    for i, p_items in enumerate(current_pallets):
        if y < 350: 
            c.showPage(); y = h_a4 - 50; c.setFont(font_name, 10)
        
        c.drawString(40, y, f"■ パレット {i+1} (商品数: {len(p_items)}個)")
        y -= 20
        
        # 図の描画
        fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], p_items, figsize=(12, 6))
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format='png', bbox_inches='tight')
        img_buf.seek(0); plt.close(fig)
        img = ImageReader(img_buf)
        c.drawImage(img, 20, y - 250, width=550, height=250, preserveAspectRatio=True)
        y -= 270
        
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# メイン処理
# ---------------------------------------------------------

st.title("📦 積載シミュレーター (統合版)")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state: st.session_state.results = []
if 'params' not in st.session_state: st.session_state.params = {}
if 'df_products' not in st.session_state: st.session_state.df_products = get_empty_data()
if 'calculated' not in st.session_state: st.session_state.calculated = False

# 1. パレット設定
with st.expander("パレット設定", expanded=True):
    c_pw, c_pd, c_ph, c_pm, c_oh = st.columns(5)
    pw_val = c_pw.number_input("幅 (mm)", value=1100, step=10)
    pd_val = c_pd.number_input("奥行 (mm)", value=1100, step=10)
    ph_val = c_ph.number_input("高さ (mm)", value=1700, step=10)
    pm_val = c_pm.number_input("Max重量(kg)", value=1000, step=10)
    oh_val = c_oh.number_input("重ね積み許容(mm)", value=30, step=5)

# 2. 商品入力 (Excel風 UI)
st.subheader("商品情報入力")
st.info("💡 Excelからコピー＆ペースト可能です。")

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    if st.button("🗑️ クリア", use_container_width=True):
        st.session_state.df_products = get_empty_data()
        st.rerun()

column_order = ["商品名", "幅(mm)", "奥行(mm)", "高さ(mm)", "重量(kg)", "数量", "優先度", "配置向き"]
edited_df = st.data_editor(
    st.session_state.df_products,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "商品名": st.column_config.TextColumn("商品名", required=True),
        "幅(mm)": st.column_config.NumberColumn("幅(mm)", min_value=0, format="%d"),
        "奥行(mm)": st.column_config.NumberColumn("奥行(mm)", min_value=0, format="%d"),
        "高さ(mm)": st.column_config.NumberColumn("高さ(mm)", min_value=0, format="%d"),
        "重量(kg)": st.column_config.NumberColumn("重量(kg)", min_value=0.0, format="%.1f"),
        "数量": st.column_config.NumberColumn("数量", min_value=0, format="%d"),
        "優先度": st.column_config.NumberColumn("優先度", min_value=1, help="大きいほど先に積む"),
        "配置向き": st.column_config.SelectboxColumn("配置向き", options=["自動", "横固定", "縦固定"], default="自動"),
    }
)

# 3. 計算ロジック (効率重視版 + ID付与)
def run_optimization():
    raw_items = []
    colors = ['#ff9999', '#99ccff', '#99ff99', '#ffff99', '#cc99ff', '#ffa07a', '#87cefa', '#f0e68c', '#dda0dd', '#90ee90']
    
    # DataFrameからデータ抽出
    for idx, row in edited_df.iterrows():
        try:
            name = str(row["商品名"])
            if not name or name == "nan" or not name.strip(): continue
            w, d, h = int(row["幅(mm)"]), int(row["奥行(mm)"]), int(row["高さ(mm)"])
            g, n = float(row["重量(kg)"]), int(row["数量"])
            prio = int(row["優先度"]) if "優先度" in row else 1
            orient = str(row["配置向き"]) if "配置向き" in row else "自動"
            
            if n <= 0 or w <= 0: continue
            
            col = colors[idx % len(colors)]
            
            # 手動移動のために、あえて「1個ずつ」のオブジェクトとして生成
            for i in range(n):
                raw_items.append({
                    'name': name,
                    'sub_id': i + 1,
                    'w': w, 'd': d, 'h': h, 'g': g,
                    'col': col,
                    'area': w * d,
                    'prio': prio,
                    'orient': orient,
                    'uniq_id': str(uuid.uuid4()) # 移動用のユニークID
                })
        except:
            continue

    if not raw_items:
        st.error("有効な商品データがありません。")
        return

    # ソート: 優先度(降順) -> 面積(降順) -> 高さ(降順)
    raw_items.sort(key=lambda x: (-x['prio'], -x['area'], -x['h']))

    pallets = []
    PW, PD, PH = pw_val, pd_val, ph_val
    MAX_W = pm_val

    # 積み付け実行 (貪欲法 + 座標探索)
    for item in raw_items:
        placed = False
        
        # 既存パレット探索
        for p in pallets:
            if p['current_weight'] + item['g'] > MAX_W: continue
            
            # 配置候補点: (0,0,0) + 全既存アイテムの (右, 奥, 上)
            candidates = [(0,0,0)]
            for exist in p['items']:
                candidates.append((exist['x'] + exist['w'], exist['y'], exist['z'])) # 右
                candidates.append((exist['x'], exist['y'] + exist['d'], exist['z'])) # 奥
                candidates.append((exist['x'], exist['y'], exist['z'] + exist['h'])) # 上
            
            # Z(低い順) -> Y(奥) -> X(右) の順で探索
            candidates.sort(key=lambda c: (c[2], c[1], c[0]))
            
            for cx, cy, cz in candidates:
                # 回転パターン
                orients = []
                if item['orient'] == "自動": orients = [(item['w'], item['d']), (item['d'], item['w'])]
                elif item['orient'] == "横固定": orients = [(item['w'], item['d'])]
                else: orients = [(item['d'], item['w'])]
                
                for tw, td in orients:
                    # はみ出しチェック
                    if cx + tw > PW or cy + td > PD or cz + item['h'] > PH: continue
                    
                    # 重なりチェック
                    overlap = False
                    for exist in p['items']:
                        if (cx < exist['x'] + exist['w'] and cx + tw > exist['x'] and
                            cy < exist['y'] + exist['d'] and cy + td > exist['y'] and
                            cz < exist['z'] + exist['h'] and cz + item['h'] > exist['z']):
                            overlap = True; break
                    if overlap: continue
                    
                    # 物理安定性チェック (Z>0の場合、直下に支持体が必要)
                    if cz > 0:
                        supported = False
                        center_x = cx + tw / 2
                        center_y = cy + td / 2
                        for exist in p['items']:
                            if abs((exist['z'] + exist['h']) - cz) < 1.0: # 直下
                                if (exist['x'] <= center_x <= exist['x'] + exist['w'] and
                                    exist['y'] <= center_y <= exist['y'] + exist['d']):
                                    supported = True; break
                        if not supported: continue
                    
                    # 配置決定
                    item['x'], item['y'], item['z'] = cx, cy, cz
                    item['w'], item['d'] = tw, td
                    p['items'].append(item)
                    p['current_weight'] += item['g']
                    placed = True
                    break
                if placed: break
            if placed: break
        
        # 新規パレット作成
        if not placed:
            new_p = {'items': [], 'current_weight': 0}
            # (0,0,0)に配置トライ
            tw, td = item['w'], item['d']
            # 回転考慮
            if (tw > PW or td > PD) and (td <= PW and tw <= PD):
                 tw, td = td, tw
            
            if tw <= PW and td <= PD and item['h'] <= PH:
                item['x'], item['y'], item['z'] = 0, 0, 0
                item['w'], item['d'] = tw, td
                new_p['items'].append(item)
                new_p['current_weight'] += item['g']
                pallets.append(new_p)
    
    st.session_state.results = [p['items'] for p in pallets]
    st.session_state.params = {'PW': PW, 'PD': PD, 'PH': PH, 'MAX_W': MAX_W}
    st.session_state.calculated = True

# 計算実行ボタン
if st.button("計算実行 (初期化)", type="primary"):
    with st.spinner("最適化計算中..."):
        run_optimization()

# ---------------------------------------------------------
# 結果表示 & 編集エリア
# ---------------------------------------------------------
if st.session_state.calculated and st.session_state.results:
    results = st.session_state.results
    params = st.session_state.params
    
    st.markdown("---")
    st.subheader(f"計算結果: パレット {len(results)}枚")
    
    # PDF DL
    pdf_dat = create_pdf(results, params)
    st.download_button("PDFレポート ダウンロード", pdf_dat, "report.pdf", "application/pdf")

    # 現在の状態を表示 (5面図で表示)
    for i, items in enumerate(results):
        with st.container():
            st.markdown(f"#### パレット No.{i+1}")
            total_w = sum([it['g'] for it in items])
            st.caption(f"商品数: {len(items)}個 | 総重量: {total_w:.1f} kg")
            
            # 5面図の描画 (不透明版)
            fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], items)
            st.pyplot(fig)
    
    st.markdown("---")
    st.header("🛠️ 手動調整モード")
    st.caption("指定した商品を、別のパレットや別の箱の上に移動できます。**底面積70%未満の不安定な積み方はエラーになります。**")

    with st.form("move_form"):
        c1, c2, c3 = st.columns(3)
        
        # 移動元選択リスト作成
        move_options = []
        for p_idx, p_items in enumerate(results):
            # Zが高い順（積み直しやすい順）に並べて表示
            sorted_items = sorted(enumerate(p_items), key=lambda x: x[1]['z'], reverse=True)
            for it_idx, it in sorted_items:
                label = f"P{p_idx+1}: {it['name']} #{it['sub_id']} (z={it['z']})"
                value = (p_idx, it_idx) # (パレットidx, リスト内idx)
                move_options.append((label, value))
        
        selected_src = c1.selectbox("1. 移動する商品", options=[m[1] for m in move_options], 
                                    format_func=lambda x: [m[0] for m in move_options if m[1]==x][0])
        
        # 移動先パレット
        pallet_options = list(range(len(results))) + [len(results)] # 最後は新規
        dst_p_idx = c2.selectbox("2. 移動先パレット", options=pallet_options, 
                                 format_func=lambda x: f"パレット {x+1}" if x < len(results) else "新規パレット作成")

        # 移動先土台
        # 自分自身は除外
        dst_base_options = [("床 (空きスペースに追加)", None)]
        if dst_p_idx < len(results):
            # 移動先パレットにある商品一覧
            for it_idx, it in enumerate(results[dst_p_idx]):
                # 移動元と同じアイテムならスキップ
                if selected_src[0] == dst_p_idx and selected_src[1] == it_idx: continue
                
                label = f"{it['name']} #{it['sub_id']} の上 (z={it['z']+it['h']})"
                dst_base_options.append((label, it_idx))
        
        selected_dst_base = c3.selectbox("3. 配置場所（土台）", options=[d[1] for d in dst_base_options],
                                         format_func=lambda x: [d[0] for d in dst_base_options if d[1]==x][0])

        submit = st.form_submit_button("移動実行")
    
    if submit:
        src_p_idx, src_it_idx_real = selected_src # src_it_idx_real は results[p] の中のインデックス
        dst_base_idx = selected_dst_base
        
        # オブジェクト参照
        src_pallet = results[src_p_idx]
        target_item = src_pallet[src_it_idx_real]
        
        # 移動先パレット準備
        if dst_p_idx == len(results):
            results.append([])
        dst_pallet = results[dst_p_idx]

        error_msg = None
        new_x, new_y, new_z = 0, 0, 0
        
        # --- ルールチェック ---
        # A. 土台指定 (On Top)
        if dst_base_idx is not None:
            base_item = dst_pallet[dst_base_idx]
            
            # 1. 70%ルール (安全性)
            base_area = base_item['w'] * base_item['d']
            top_area = target_item['w'] * target_item['d']
            if base_area < (top_area * 0.7):
                error_msg = f"⚠️ エラー: 不安定です。\n土台の面積({base_area})が、上の面積({top_area})の70%未満です。"
            
            # 2. 高さ制限
            new_z = base_item['z'] + base_item['h']
            if new_z + target_item['h'] > params['PH']:
                error_msg = f"⚠️ エラー: 高さ制限を超えます。"
            
            # 座標決定 (中央寄せ)
            new_x = base_item['x'] + (base_item['w'] - target_item['w']) / 2
            new_y = base_item['y'] + (base_item['d'] - target_item['d']) / 2
            
        else:
            # B. 床配置 (Floor)
            # 簡易的に、既存アイテムの最大Xの右隣に置く (重なり回避の簡易実装)
            new_z = 0
            if not dst_pallet:
                new_x, new_y = 0, 0
            else:
                # パレット内で右端を探す
                max_x_item = max(dst_pallet, key=lambda x: x['x'] + x['w'])
                new_x = max_x_item['x'] + max_x_item['w']
                new_y = 0
                
                # はみ出しチェック
                if new_x + target_item['w'] > params['PW']:
                    error_msg = "⚠️ 床配置スペースがありません（右側に空きなし）。"

        if error_msg:
            st.error(error_msg)
        else:
            # 移動実行
            # 1. コピー作成・座標更新
            moved_item = target_item.copy()
            moved_item['x'], moved_item['y'], moved_item['z'] = new_x, new_y, new_z
            
            # 2. 元リストから削除
            # indexはずれる可能性があるので、ID等で安全に削除するか、単純にpop
            # ここではUIがリロードされるのでpopでよい
            results[src_p_idx].pop(src_it_idx_real)
            
            # 3. 先リストに追加
            dst_pallet.append(moved_item)
            
            st.success(f"移動完了: {moved_item['name']}")
            st.rerun()
