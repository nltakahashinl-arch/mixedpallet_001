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

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="パレット積載シミュレーター (編集機能付)")

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
def parse_ids(id_str):
    if not id_str: return []
    res = set()
    try:
        id_str = str(id_str).replace('，', ',').replace('－', '-').replace(' ', '')
        parts = id_str.split(',')
        for p in parts:
            if '-' in p:
                start, end = p.split('-')
                start, end = int(start), int(end)
                if start > end: start, end = end, start
                for i in range(start, end + 1):
                    res.add(i)
            else:
                if p.isdigit():
                    res.add(int(p))
    except:
        pass
    return list(res)

# --- 描画関数 ---
def draw_pallet_figure(PW, PD, PH, p_items, figsize=(12, 6)):
    fig = plt.figure(figsize=figsize)
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1])

    # 1. 上面図 (配置図)
    ax_top = fig.add_subplot(gs[0])
    ax_top.set_aspect('equal')
    ax_top.add_patch(patches.Rectangle((0,0), PW, PD, fill=False, lw=2))
    
    # Z順（下から）に描画
    sorted_items = sorted(p_items, key=lambda x: x.get('z', 0))
    for b in sorted_items:
        ax_top.add_patch(patches.Rectangle((b['x'], b['y']), b['w'], b['d'], 
                                           facecolor=b['col'], edgecolor='black', alpha=0.9))
        
        # テキスト表示
        info_txt = f"{b['disp_name']}\n(ID:{b['uniq_id'][:4]})"
        ax_top.text(b['x'] + b['w']/2, b['y'] + b['d']/2, info_txt, 
                    ha='center', va='center', fontsize=8, color='black', clip_on=True)

    ax_top.set_xlim(-50, PW+50); ax_top.set_ylim(-50, PD+50); ax_top.invert_yaxis()
    ax_top.set_title("上面図 (Top View)", fontweight='bold')

    # 2. 正面図 (積み上げ確認用)
    ax_front = fig.add_subplot(gs[1])
    ax_front.set_aspect('equal', adjustable='box') # アスペクト比維持
    ax_front.add_patch(patches.Rectangle((0,0), PW, PH, fill=False, lw=2))

    for b in sorted_items:
        # 正面図なので X軸(横) と Z軸(高さ) を使う
        ax_front.add_patch(patches.Rectangle((b['x'], b['z']), b['w'], b['h_total'], 
                                             facecolor=b['col'], edgecolor='black', alpha=0.9))
        ax_front.text(b['x'] + b['w']/2, b['z'] + b['h_total']/2, b['disp_name'], 
                      ha='center', va='center', fontsize=8, color='black', clip_on=True)
    
    ax_front.set_xlim(-50, PW+50); ax_front.set_ylim(0, PH+100)
    ax_front.set_title("正面図 (Front View)", fontweight='bold')

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
    c.drawString(40, y, "パレット積載シミュレーション結果")
    y -= 30
    c.setFont(font_name, 10)
    
    for i, p_items in enumerate(current_pallets):
        if y < 300: 
            c.showPage(); y = h_a4 - 50; c.setFont(font_name, 10)
        
        c.drawString(40, y, f"■ パレット {i+1}")
        y -= 20
        
        # 図の描画
        fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], p_items, figsize=(10, 4))
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format='png', bbox_inches='tight')
        img_buf.seek(0); plt.close(fig)
        img = ImageReader(img_buf)
        c.drawImage(img, 40, y - 200, width=500, height=200, preserveAspectRatio=True)
        y -= 220
        
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# メイン処理
# ---------------------------------------------------------

st.title("📦 積載シミュレーター（手動調整機能付き）")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state: st.session_state.results = []
if 'params' not in st.session_state: st.session_state.params = {}
if 'move_log' not in st.session_state: st.session_state.move_log = []

# 1. 設定入力
with st.sidebar:
    st.header("パレット設定")
    p_w = st.number_input("幅 (mm)", 1100, step=10)
    p_d = st.number_input("奥行 (mm)", 1100, step=10)
    p_h = st.number_input("高さ (mm)", 1700, step=10)
    p_kg = st.number_input("最大重量 (kg)", 1000, step=10)
    oh_val = st.number_input("重ね許容 (mm)", 30, step=5)

# 2. データ入力
default_csv = """# 品番, 幅, 奥行, 高さ, 重量, 個数
A-001, 250, 200, 225, 5.0, 14
B-002, 414, 214, 200, 5.0, 20
C-004, 314, 214, 200, 5.0, 18
D-002, 450, 300, 230, 5.0, 30
F-001, 440, 280, 130, 5.0, 40
B-003, 470, 390, 150, 5.0, 6
"""
input_text = st.text_area("入力データ (CSV)", default_csv, height=150)

# 3. 計算ロジック
def run_optimization():
    # 入力パース
    raw_items = []
    colors = ['#ff9999', '#99ccff', '#99ff99', '#ffff99', '#cc99ff', '#ffa07a', '#87cefa', '#f0e68c']
    try:
        rows = input_text.strip().split('\n')
        for idx, row in enumerate(rows):
            if row.startswith("#") or not row.strip(): continue
            p = [x.strip() for x in row.split(',')]
            name = p[0]
            w, d, h = int(p[1]), int(p[2]), int(p[3])
            g = float(p[4])
            n = int(p[5])
            col = colors[idx % len(colors)]
            
            for i in range(n):
                # ブロック化せず、個別に扱う（今回は移動機能のため、個々の箱を管理）
                # しかし効率計算のためには一旦まとめる必要があるが、
                # 今回の要件「移動」のため、計算後にブロック情報を保持する。
                
                # ここでは簡易化のため、1個＝1ブロックとして扱い、
                # 後でスタックロジックで積み上げる形にする
                raw_items.append({
                    'name': name, 'sub_id': i+1,
                    'disp_name': f"{name} #{i+1}",
                    'w': w, 'd': d, 'h': h, 'g': g,
                    'col': col, 'area': w*d,
                    'uniq_id': str(uuid.uuid4()) # 移動用の一意なID
                })
    except Exception as e:
        st.error(f"データ読込エラー: {e}")
        return

    # ソート（底面積が大きい順）
    raw_items.sort(key=lambda x: x['area'], reverse=True)

    pallets = []
    
    for item in raw_items:
        placed = False
        
        # 既存パレットへ積載トライ
        for p in pallets:
            # 1. 既存アイテムの上に乗るか？ (簡単なスタック判定)
            # 全アイテムを探索し、乗せられる場所を探す
            # Zが高い場所（＝積みあがっている場所）を優先したいが、今回は単純な走査
            
            # 候補: 床(z=0) または 他のアイテムの上(z=item.z + item.h)
            # ここでは「Method 3」で動かすベースを作るため、簡易的な最適化を行う
            
            # まず「隙間」を探す（床配置）
            # 簡易ロジック: X, Yをグリッドで探すのは重いので、
            # 「既存アイテムの右」か「既存アイテムの奥」を候補点とする
            
            candidate_points = [(0,0,0)]
            for exist in p['items']:
                # 既存アイテムの上
                candidate_points.append((exist['x'], exist['y'], exist['z'] + exist['h']))
                # 既存アイテムの右
                candidate_points.append((exist['x'] + exist['w'], exist['y'], 0))
                # 既存アイテムの奥
                candidate_points.append((exist['x'], exist['y'] + exist['d'], 0))
            
            # Zが低い順、Yが小さい順、Xが小さい順にソート
            candidate_points.sort(key=lambda c: (c[2], c[1], c[0]))
            
            best_pos = None
            
            for cx, cy, cz in candidate_points:
                # はみ出しチェック
                if cx + item['w'] > p_w or cy + item['d'] > p_d or cz + item['h'] > p_h:
                    # 回転トライ
                    if cx + item['d'] <= p_w and cy + item['w'] <= p_d and cz + item['h'] <= p_h:
                        # 回転してセット
                        item['w'], item['d'] = item['d'], item['w']
                    else:
                        continue # この場所はダメ
                
                # 重なりチェック
                overlap = False
                for exist in p['items']:
                    if (cx < exist['x'] + exist['w'] and cx + item['w'] > exist['x'] and
                        cy < exist['y'] + exist['d'] and cy + item['d'] > exist['y'] and
                        cz < exist['z'] + exist['h'] and cz + item['h'] > exist['z']):
                        overlap = True; break
                if overlap: continue

                # 空中浮遊チェック (z>0の場合)
                if cz > 0:
                    supported = False
                    item_center_x = cx + item['w']/2
                    item_center_y = cy + item['d']/2
                    for exist in p['items']:
                        if exist['z'] + exist['h'] == cz: # 直下にある
                            # 中心が乗っているか
                            if (exist['x'] <= item_center_x <= exist['x'] + exist['w'] and
                                exist['y'] <= item_center_y <= exist['y'] + exist['d']):
                                supported = True; break
                    if not supported: continue
                
                # ここまで来たら配置OK
                best_pos = (cx, cy, cz)
                break
            
            if best_pos:
                item['x'], item['y'], item['z'] = best_pos
                item['h_total'] = item['h'] # 描画用
                p['items'].append(item)
                p['current_weight'] += item['g']
                placed = True
                break
        
        if not placed:
            # 新規パレット
            new_p = {'items': [], 'current_weight': 0}
            # (0,0,0)に配置
            if item['w'] <= p_w and item['d'] <= p_d:
                item['x'], item['y'], item['z'] = 0, 0, 0
                item['h_total'] = item['h']
                new_p['items'].append(item)
                new_p['current_weight'] += item['g']
                pallets.append(new_p)
            else:
                # 回転して入るなら
                 if item['d'] <= p_w and item['w'] <= p_d:
                    item['w'], item['d'] = item['d'], item['w']
                    item['x'], item['y'], item['z'] = 0, 0, 0
                    item['h_total'] = item['h']
                    new_p['items'].append(item)
                    new_p['current_weight'] += item['g']
                    pallets.append(new_p)
    
    st.session_state.results = [p['items'] for p in pallets]
    st.session_state.params = {'PW': p_w, 'PD': p_d, 'PH': p_h, 'MAX_W': p_kg}
    st.session_state.move_log = []

# --- ボタン ---
if st.button("計算実行 (初期化)", type="primary"):
    with st.spinner("計算中..."):
        run_optimization()

# ---------------------------------------------------------
# 結果表示 & 編集エリア
# ---------------------------------------------------------
if st.session_state.results:
    results = st.session_state.results
    params = st.session_state.params
    
    st.markdown("---")
    st.subheader(f"計算結果: パレット {len(results)}枚")
    
    # PDF DL
    pdf_dat = create_pdf(results, params)
    st.download_button("PDFレポート ダウンロード", pdf_dat, "report.pdf", "application/pdf")

    # 現在の状態を表示
    for i, items in enumerate(results):
        with st.container():
            col_info, col_img = st.columns([1, 2])
            with col_info:
                st.info(f"**パレット No.{i+1}**")
                total_w = sum([it['g'] for it in items])
                st.write(f"商品数: {len(items)}個")
                st.write(f"総重量: {total_w:.1f} kg")
            with col_img:
                fig = draw_pallet_figure(params['PW'], params['PD'], params['PH'], items)
                st.pyplot(fig)
    
    st.markdown("---")
    st.header("🛠️ 手動調整モード")
    st.markdown("計算結果の一部を動かします。**移動先が不安定（底面積比70%未満）な場合はエラーになります。**")

    # --- 移動UI ---
    with st.form("move_form"):
        c1, c2, c3 = st.columns(3)
        
        # 1. 移動元の商品を選択
        # リスト作成: "P1: 商品A(ID...)"
        move_options = []
        for p_idx, p_items in enumerate(results):
            for it_idx, it in enumerate(p_items):
                label = f"P{p_idx+1}: {it['disp_name']} (z={it['z']})"
                value = (p_idx, it_idx) # 識別子
                move_options.append((label, value))
        
        selected_src = c1.selectbox("1. 移動する商品", options=[m[1] for m in move_options], 
                                    format_func=lambda x: [m[0] for m in move_options if m[1]==x][0])
        
        # 2. 移動先パレット
        # 既存 + 新規パレット
        pallet_options = list(range(len(results))) + [len(results)] # 最後は新規
        dst_p_idx = c2.selectbox("2. 移動先パレット", options=pallet_options, 
                                 format_func=lambda x: f"パレット {x+1}" if x < len(results) else "新規パレット作成")

        # 3. 移動先の商品（土台）を選択
        # 選択されたパレット内のアイテム + "床(空きスペース)"
        dst_base_options = [("床 (空きスペースに追加)", None)]
        if dst_p_idx < len(results):
            for it_idx, it in enumerate(results[dst_p_idx]):
                # 自分自身には乗れない
                if selected_src[0] == dst_p_idx and selected_src[1] == it_idx: continue
                
                label = f"{it['disp_name']} の上 (z={it['z']+it['h']})"
                dst_base_options.append((label, it_idx))
        
        selected_dst_base = c3.selectbox("3. 配置場所（土台）", options=[d[1] for d in dst_base_options],
                                         format_func=lambda x: [d[0] for d in dst_base_options if d[1]==x][0])

        submit = st.form_submit_button("移動実行")
    
    if submit:
        src_p_idx, src_it_idx = selected_src
        dst_base_idx = selected_dst_base
        
        # オブジェクト取得
        src_pallet = results[src_p_idx]
        target_item = src_pallet[src_it_idx]
        
        # 移動先パレット準備
        if dst_p_idx == len(results):
            results.append([]) # 新規作成
        dst_pallet = results[dst_p_idx]

        error_msg = None
        
        # --- ルールチェック ---
        
        # A. 土台がある場合 (On Top)
        if dst_base_idx is not None:
            base_item = dst_pallet[dst_base_idx]
            
            # 1. 70%ルール (安全性)
            # 下の面積 * 0.7 > 上の面積 ならNG? 逆、
            # 下の面積 < 上の面積 * 0.7 ならNG (上が大きすぎて不安定)
            # ユーザー要件: "下になるブロックの低面積が上の商品の低面積の70%に満たない場合は不安定"
            # => BaseArea < TopArea * 0.7  ---> Error
            base_area = base_item['w'] * base_item['d']
            top_area = target_item['w'] * target_item['d']
            
            if base_area < (top_area * 0.7):
                error_msg = f"⚠️ 不安定です！\n下の面積({base_area})が、上の面積({top_area})の70%未満です。"
            
            # 2. 高さ制限
            new_z = base_item['z'] + base_item['h']
            if new_z + target_item['h'] > params['PH']:
                error_msg = f"⚠️ 高さオーバーです (積載後: {new_z + target_item['h']}mm > 制限: {params['PH']}mm)"

            # 座標決定
            new_x = base_item['x'] + (base_item['w'] - target_item['w']) / 2 # 中央寄せ
            new_y = base_item['y'] + (base_item['d'] - target_item['d']) / 2
            
        else:
            # B. 床配置 (Floor)
            # 単純に「移動先パレットの既存アイテムと被らない場所」を探すのは難しいので、
            # 「右端」または「奥」に追加する簡易ロジックを採用
            # または「新規パレット」なら (0,0,0)
            new_z = 0
            
            if not dst_pallet:
                new_x, new_y = 0, 0
            else:
                # 簡易的に、既存アイテムの最大Xの隣に置く
                max_x_item = max(dst_pallet, key=lambda x: x['x'] + x['w'])
                new_x = max_x_item['x'] + max_x_item['w']
                new_y = 0 # Yは0から
                
                # はみ出すならエラー
                if new_x + target_item['w'] > params['PW']:
                     # 次の列（Y方向）を試す？
                     # 今回は簡易実装のため、Xオーバーならエラーとする
                     error_msg = "⚠️ 床配置スペースがありません（右側に空きなし）"

        # --- 実行 ---
        if error_msg:
            st.error(error_msg)
        else:
            # 移動処理
            # 元のリストから削除 (IDで特定して削除しないとインデックスずれる可能性ありだが、今回は再計算なしなのでpopでOK)
            # ただし pop するとインデックスが変わるので、リスト操作は慎重に
            
            # コピーを作成して追加
            item_to_move = target_item.copy()
            item_to_move['x'] = new_x
            item_to_move['y'] = new_y
            item_to_move['z'] = new_z
            
            # 元のパレットから削除
            results[src_p_idx].pop(src_it_idx)
            
            # もし元のパレットが空になったら削除する？ -> いや、番号ずれるので残すか、詰め処理するか。
            # 今回は空リストを残す仕様にします
            
            # 移動先に追加
            dst_pallet.append(item_to_move)
            
            st.success(f"移動しました: {item_to_move['disp_name']}")
            st.rerun() # 画面更新
