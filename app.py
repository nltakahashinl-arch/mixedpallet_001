import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import time

# ==========================================
# 1. 積載計算ロジック (コア部分)
# ==========================================
class Item:
    def __init__(self, item_id, width, depth, height, weight, color="#69b3a2"):
        self.item_id = item_id
        self.width = int(width)
        self.depth = int(depth)
        self.height = int(height)
        self.weight = float(weight)
        self.color = color
        self.x = 0
        self.y = 0
        self.z = 0
        self.rotated = False

    @property
    def area(self):
        return self.width * self.depth

    def get_dimension(self):
        if self.rotated:
            return self.depth, self.width, self.height
        return self.width, self.depth, self.height

class Pallet:
    def __init__(self, max_w, max_d, max_h, max_weight):
        self.max_w = max_w
        self.max_d = max_d
        self.max_h = max_h
        self.max_weight = max_weight
        self.items = []

    def current_weight(self):
        return sum(item.weight for item in self.items)

    def is_overlap(self, x, y, z, w, d, h):
        for item in self.items:
            iw, id_, ih = item.get_dimension()
            if (x < item.x + iw and x + w > item.x and
                y < item.y + id_ and y + d > item.y and
                z < item.z + ih and z + h > item.z):
                return True
        return False

    def can_place(self, item, x, y, z, rotated):
        w, d, h = (item.depth, item.width, item.height) if rotated else (item.width, item.depth, item.height)
        
        if x + w > self.max_w or y + d > self.max_d or z + h > self.max_h: return False
        if self.current_weight() + item.weight > self.max_weight: return False
        if self.is_overlap(x, y, z, w, d, h): return False

        # 簡易的な支持判定（空中浮遊防止）
        if z > 0:
            supported = False
            cx, cy = x + w/2, y + d/2
            for prev in self.items:
                pw, pd, ph = prev.get_dimension()
                if prev.z + ph == z:
                     if prev.x < cx < prev.x + pw and prev.y < cy < prev.y + pd:
                         supported = True
                         break
            if not supported: return False
        return True

    def add_item(self, item):
        # 探索候補座標の生成（高速化）
        xs, ys, zs = {0}, {0}, {0}
        for i in self.items:
            iw, id_, ih = i.get_dimension()
            if i.x + iw < self.max_w: xs.add(i.x + iw)
            if i.y + id_ < self.max_d: ys.add(i.y + id_)
            if i.z + ih < self.max_h: zs.add(i.z + ih)
            
        sorted_zs = sorted(list(zs))
        sorted_ys = sorted(list(ys))
        sorted_xs = sorted(list(xs))

        for z in sorted_zs:
            if z + item.height > self.max_h: break
            for y in sorted_ys:
                for x in sorted_xs:
                    # 回転なし
                    if self.can_place(item, x, y, z, False):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = False
                        self.items.append(item)
                        return True
                    # 回転あり
                    if self.can_place(item, x, y, z, True):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = True
                        self.items.append(item)
                        return True
        return False

def optimize_loading(items, pallet_spec):
    # 【最重要】底面積が大きい順にソート（大きい岩から入れる）
    items.sort(key=lambda x: x.area, reverse=True)
    
    pallets = []
    for item in items:
        placed = False
        for pallet in pallets:
            if pallet.add_item(item):
                placed = True
                break
        if not placed:
            new_pallet = Pallet(*pallet_spec)
            new_pallet.add_item(item)
            pallets.append(new_pallet)
    return pallets

# ==========================================
# 2. 描画関数 (Matplotlibで可視化)
# ==========================================
def draw_pallet(pallet, index):
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # パレット枠
    ax.add_patch(patches.Rectangle((0, 0), pallet.max_w, pallet.max_d, fill=False, edgecolor="black", linewidth=3))
    
    # 商品描画（下にあるものから描くためにZ順ソート）
    # ※簡易的に「上から見た図」として描画します
    sorted_items = sorted(pallet.items, key=lambda i: i.z)
    
    colors = plt.cm.get_cmap("tab20", len(sorted_items))
    
    for i, item in enumerate(sorted_items):
        w, d, h = item.get_dimension()
        # 色分け
        rect = patches.Rectangle((item.x, item.y), w, d, 
                                 linewidth=1, edgecolor='black', facecolor=colors(i), alpha=0.8)
        ax.add_patch(rect)
        # テキスト（ID）
        ax.text(item.x + w/2, item.y + d/2, f"{item.item_id}\n(z={item.z})", 
                ha='center', va='center', fontsize=8, color='white', fontweight='bold')

    ax.set_xlim(-50, pallet.max_w + 50)
    ax.set_ylim(-50, pallet.max_d + 50)
    ax.set_aspect('equal')
    ax.set_title(f"Pallet No.{index+1} (Top View) - {len(pallet.items)} items")
    return fig

# ==========================================
# 3. Streamlit UI (画面表示)
# ==========================================
st.set_page_config(page_title="パレット積載シミュレーター", layout="wide")

st.title("📦 パレット積載最適化シミュレーター")
st.markdown("底面積の大きい順に自動整列し、回転も考慮して最小枚数を計算します。")

# --- サイドバー：設定 ---
st.sidebar.header("パレット設定")
p_w = st.sidebar.number_input("幅 (mm)", value=1100)
p_d = st.sidebar.number_input("奥行 (mm)", value=1100)
p_h = st.sidebar.number_input("高さ制限 (mm)", value=1700)
p_kg = st.sidebar.number_input("耐荷重 (kg)", value=1000)

# --- メイン：データ入力 ---
st.subheader("1. 商品データ入力")
default_csv = """
# 品番, 幅, 奥行, 高さ, 重量, 個数
A-001, 250, 200, 225, 5.0, 14
B-002, 414, 214, 200, 5.0, 20
C-004, 314, 214, 200, 5.0, 18
A-002, 60,  210, 180, 5.0, 5
B-001, 354, 264, 200, 5.0, 7
C-001, 10,  210, 140, 5.0, 5
D-002, 450, 300, 230, 5.0, 30
A-003, 140, 300, 220, 5.0, 20
F-001, 440, 280, 130, 5.0, 40
F-002, 500, 240, 230, 5.0, 4
C-005, 460, 285, 170, 5.0, 15
B-003, 470, 390, 150, 5.0, 6
"""
input_text = st.text_area("CSVデータ貼り付け (品番, W, D, H, kg, 個数)", value=default_csv.strip(), height=300)

if st.button("計算実行 (Optimize)", type="primary"):
    # データのパース
    try:
        items = []
        rows = input_text.strip().split('\n')
        for row in rows:
            if row.startswith("#") or row.strip() == "": continue
            parts = [p.strip() for p in row.split(',')]
            pid, w, d, h, kg, qty = parts[0], int(parts[1]), int(parts[2]), int(parts[3]), float(parts[4]), int(parts[5])
            for _ in range(qty):
                items.append(Item(pid, w, d, h, kg))
        
        st.success(f"データ読み込み完了: 商品総数 {len(items)}個")
        
        # 計算開始
        start_ts = time.time()
        with st.spinner('最適配置を計算中...'):
            result_pallets = optimize_loading(items, (p_w, p_d, p_h, p_kg))
        end_ts = time.time()
        
        # 結果表示
        st.divider()
        st.header(f"計算結果: 必要パレット {len(result_pallets)}枚")
        st.caption(f"計算時間: {end_ts - start_ts:.2f}秒")
        
        cols = st.columns(len(result_pallets))
        
        for i, pallet in enumerate(result_pallets):
            with cols[i] if i < len(cols) else st.container():
                st.subheader(f"No.{i+1}")
                st.write(f"積載数: **{len(pallet.items)}個**")
                st.write(f"重量:
