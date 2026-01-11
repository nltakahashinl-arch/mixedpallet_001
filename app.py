import operator

class Item:
    def __init__(self, item_id, width, depth, height, weight):
        self.item_id = item_id
        self.width = width
        self.depth = depth
        self.height = height
        self.weight = weight
        # 積載時の座標と回転状態
        self.x = 0
        self.y = 0
        self.z = 0
        self.rotated = False

    @property
    def area(self):
        return self.width * self.depth

    @property
    def volume(self):
        return self.width * self.depth * self.height

    def get_dimension(self):
        # 回転状態に応じて現在のW, Dを返す
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
        # 既存のアイテムと重ならないかチェック
        for item in self.items:
            iw, id_, ih = item.get_dimension()
            # 3次元での衝突判定
            if (x < item.x + iw and x + w > item.x and
                y < item.y + id_ and y + d > item.y and
                z < item.z + ih and z + h > item.z):
                return True
        return False

    def can_place(self, item, x, y, z, rotated):
        # 回転状態でのサイズ取得
        w, d, h = (item.depth, item.width, item.height) if rotated else (item.width, item.depth, item.height)

        # 1. パレット範囲内か
        if x + w > self.max_w or y + d > self.max_d or z + h > self.max_h:
            return False
        
        # 2. 重量制限
        if self.current_weight() + item.weight > self.max_weight:
            return False

        # 3. 他の商品との重なり
        if self.is_overlap(x, y, z, w, d, h):
            return False

        # 4. 空中に浮いていないか（簡易サポート判定）
        # Z=0 (床)ならOK。それ以外は直下に支持体が必要。
        # ※厳密な物理シミュレーションではなく、接触面積チェックで簡易判定
        if z > 0:
            supported = False
            for prev in self.items:
                pw, pd, ph = prev.get_dimension()
                # 直下(prevの上面が今のzと同じ)にあり、かつ重なりがあるか
                if (prev.z + ph == z and
                    x < prev.x + pw and x + w > prev.x and
                    y < prev.y + pd and y + d > prev.y):
                    supported = True
                    break
            if not supported:
                return False

        return True

    def add_item(self, item):
        # 空間探索分解能 (mm) - 小さいほど精密だが遅い
        step = 10 
        
        # Z軸（高さ）方向へ積み上げ
        # 既存アイテムの天面高さ候補リストを作成してループを減らす
        z_candidates = [0] + [i.z + i.get_dimension()[2] for i in self.items]
        z_candidates = sorted(list(set(z_candidates)))

        for z in z_candidates:
            if z + item.height > self.max_h:
                break
            
            # Y軸方向
            for y in range(0, self.max_d, step):
                # X軸方向
                for x in range(0, self.max_w, step):
                    
                    # まず回転なしでトライ
                    if self.can_place(item, x, y, z, False):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = False
                        self.items.append(item)
                        return True
                    
                    # ダメなら回転してトライ（自動回転ロジック）
                    if self.can_place(item, x, y, z, True):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = True
                        self.items.append(item)
                        return True
                        
        return False

def optimize_loading(order_list, pallet_spec):
    """
    order_list: [(id, w, d, h, weight, qty), ...]
    pallet_spec: (max_w, max_d, max_h, max_weight)
    """
    
    # 1. すべての商品を個別のItemインスタンスに展開
    all_items = []
    for info in order_list:
        p_id, w, d, h, weight, qty = info
        for _ in range(qty):
            all_items.append(Item(p_id, w, d, h, weight))

    # ---------------------------------------------------------
    # 【最重要修正】 ソートロジックの実装
    # 底面積(w*d)が大きい順に並び替える。
    # これにより「大きな岩を先に入れ、隙間に砂利を入れる」挙動になる。
    # ---------------------------------------------------------
    all_items.sort(key=lambda x: x.area, reverse=True)

    pallets = []
    
    # 商品を順番に処理
    for item in all_items:
        placed = False
        
        # 既存のパレットに乗るか試す
        for pallet in pallets:
            if pallet.add_item(item):
                placed = True
                break
        
        # 乗らなければ新しいパレットを追加
        if not placed:
            new_pallet = Pallet(*pallet_spec)
            new_pallet.add_item(item) # 新パレットなら必ず乗るはず（単体でオーバーしてなければ）
            pallets.append(new_pallet)

    return pallets

# ==========================================
# 実行部 (今回のデータを入力)
# ==========================================
if __name__ == "__main__":
    # パレット仕様: 1100x1100x1700, 1000kg
    SPEC = (1100, 1100, 1700, 1000)

    # 入力データ (ID, W, D, H, Wt, Qty)
    # ※B-002はレポートの図から推測し414mmとしています（14mmは誤記と判断）
    input_data = [
        ("A-001", 250, 200, 225, 5.0, 14),
        ("B-002", 414, 214, 200, 5.0, 20), 
        ("C-004", 314, 214, 200, 5.0, 18),
        ("A-002", 60,  210, 180, 5.0, 5),
        ("B-001", 354, 264, 200, 5.0, 7),
        ("C-001", 10,  210, 140, 5.0, 5),
        ("D-002", 450, 300, 230, 5.0, 30),
        ("A-003", 140, 300, 220, 5.0, 20),
        ("F-001", 440, 280, 130, 5.0, 40),
        ("F-002", 500, 240, 230, 5.0, 4),
        ("C-005", 460, 285, 170, 5.0, 15),
        ("B-003", 470, 390, 150, 5.0, 6),
    ]

    result_pallets = optimize_loading(input_data, SPEC)

    print(f"計算結果: パレット総数 {len(result_pallets)}枚")
    print("-" * 30)
    for i, p in enumerate(result_pallets):
        print(f"パレット No.{i+1}")
        print(f"  積載個数: {len(p.items)}個")
        print(f"  総重量: {p.current_weight()}kg")
        # デバッグ用: 積まれた商品の上位いくつかを表示
        top_items = [item.item_id for item in p.items[:5]]
        print(f"  初期配置商品(土台): {top_items} ...")
        print("-" * 30)
