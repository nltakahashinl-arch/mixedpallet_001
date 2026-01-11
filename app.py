import time

class Item:
    def __init__(self, item_id, width, depth, height, weight):
        self.item_id = item_id
        self.width = int(width)
        self.depth = int(depth)
        self.height = int(height)
        self.weight = float(weight)
        # 積載位置と回転状態
        self.x = 0
        self.y = 0
        self.z = 0
        self.rotated = False

    @property
    def area(self):
        return self.width * self.depth

    def get_dimension(self):
        # 回転している場合は幅と奥行きを入れ替えて返す
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
        # 既存の荷物と重なっていないかチェック
        for item in self.items:
            iw, id_, ih = item.get_dimension()
            if (x < item.x + iw and x + w > item.x and
                y < item.y + id_ and y + d > item.y and
                z < item.z + ih and z + h > item.z):
                return True
        return False

    def can_place(self, item, x, y, z, rotated):
        w, d, h = (item.depth, item.width, item.height) if rotated else (item.width, item.depth, item.height)
        
        # 1. パレットからはみ出していないか
        if x + w > self.max_w or y + d > self.max_d or z + h > self.max_h:
            return False
        
        # 2. 重量制限
        if self.current_weight() + item.weight > self.max_weight:
            return False

        # 3. 重なりチェック
        if self.is_overlap(x, y, z, w, d, h):
            return False

        # 4. 空中に浮いていないか（簡易物理チェック）
        # 床(z=0)以外の場合、直下に支える荷物があるか確認
        if z > 0:
            supported = False
            item_center_x = x + w / 2
            item_center_y = y + d / 2
            for prev in self.items:
                pw, pd, ph = prev.get_dimension()
                # 直下の段(prevの上面 == 今のz)にあり、かつ中心点が乗っているか
                if prev.z + ph == z:
                     if (prev.x < item_center_x < prev.x + pw and
                         prev.y < item_center_y < prev.y + pd):
                         supported = True
                         break
            if not supported:
                return False

        return True

    def add_item(self, item):
        # 【高速化の肝】全座標ではなく、「既存の荷物の隣や上」だけを候補として探索する
        xs = {0}
        ys = {0}
        zs = {0}
        
        for i in self.items:
            iw, id_, ih = i.get_dimension()
            if i.x + iw < self.max_w: xs.add(i.x + iw)
            if i.y + id_ < self.max_d: ys.add(i.y + id_)
            if i.z + ih < self.max_h: zs.add(i.z + ih)
            
        # 探索順序: 低い場所(Z) -> 奥(Y) -> 手前・右(X)
        sorted_zs = sorted(list(zs))
        sorted_ys = sorted(list(ys))
        sorted_xs = sorted(list(xs))

        for z in sorted_zs:
            if z + item.height > self.max_h:
                break
            for y in sorted_ys:
                for x in sorted_xs:
                    # まずそのままの向きで試す
                    if self.can_place(item, x, y, z, False):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = False
                        self.items.append(item)
                        return True
                    
                    # ダメなら90度回転して試す
                    if self.can_place(item, x, y, z, True):
                        item.x, item.y, item.z = x, y, z
                        item.rotated = True
                        self.items.append(item)
                        return True
        return False

def optimize_loading(order_list, pallet_spec):
    # データを展開
    all_items = []
    for info in order_list:
        p_id, w, d, h, weight, qty = info
        for _ in range(qty):
            all_items.append(Item(p_id, w, d, h, weight))

    # 【重要】底面積（幅×奥行）が大きい順にソート
    # これにより、大きな荷物を土台にし、小さな荷物を隙間に詰める動作になります
    all_items.sort(key=lambda x: x.area, reverse=True)

    pallets = []
    
    # 積み込み実行
    for item in all_items:
        placed = False
        # 既存パレットに乗るか確認
        for pallet in pallets:
            if pallet.add_item(item):
                placed = True
                break
        
        # 乗らなければ新しいパレットを用意
        if not placed:
            new_pallet = Pallet(*pallet_spec)
            new_pallet.add_item(item)
            pallets.append(new_pallet)

    return pallets

# ==========================================
# 実行部分
# ==========================================
if __name__ == "__main__":
    # パレット仕様: 1100x1100x1700, 1000kg
    SPEC = (1100, 1100, 1700, 1000)

    # 入力データ (ID, 幅, 奥行, 高さ, 重量, 個数)
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

    print("計算を開始します...")
    start_time = time.time()
    
    result_pallets = optimize_loading(input_data, SPEC)
    
    end_time = time.time()
    print(f"計算完了: {end_time - start_time:.2f}秒")
    print("-" * 30)
    print(f"必要パレット総数: {len(result_pallets)}枚")
    print("-" * 30)
    
    for i, p in enumerate(result_pallets):
        print(f"パレット No.{i+1}")
        print(f"  積載個数: {len(p.items)}個")
        print(f"  総重量: {p.current_weight()}kg")
        print("-" * 30)
