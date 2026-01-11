
# --- ID範囲解析関数 ---
def parse_ids(id_str):
    """ '1-3, 5' のような文字列を [1, 2, 3, 5] というリストに変換する """
if not id_str: return []
res = set()
try:
        # 全角数字を半角に、スペース削除
id_str = str(id_str).replace('，', ',').replace('－', '-').replace(' ', '')
parts = id_str.split(',')
for p in parts:
@@ -412,11 +410,10 @@ def get_empty_data():
PW, PD, PH = pw_val, pd_val, ph_val
MAX_W, OH = pm_val, oh_val

    # オーバーライド情報の整理 (ID範囲対応)
block_overrides = {}
for _, row in block_override_df.iterrows():
if row["商品名"] and row["ID(番号)"]:
            ids = parse_ids(row["ID(番号)"]) # 文字列をリストに変換
            ids = parse_ids(row["ID(番号)"])
for i in ids:
key = (str(row["商品名"]), i)
block_overrides[key] = {
@@ -450,7 +447,7 @@ def get_empty_data():

col = colors[idx % len(colors)]

            # 集計用リストへの追加（PDF用）
            # 集計用リストへの追加
items.append({
'name': name, 'w': w, 'd': d, 'h': h, 
'g': g, 'n': n, 'col': col, 'id': idx
@@ -482,8 +479,9 @@ def get_empty_data():
if not raw_items:
st.error("計算可能な商品データがありません。")
else:
        # グループ化ロジック (同じ条件の箱をまとめてブロック化)
        raw_items.sort(key=lambda x: (-x['prio'], -x['w']*x['d'], -x['h'], x['name'], x['sub_id']))
        # --- 重要: 並び順を「優先度」→「ID順」で厳格化 ---
        # これにより、指示のない「自動」ブロックが勝手に割り込むのを防ぐ
        raw_items.sort(key=lambda x: (-x['prio'], x['p_id'], x['sub_id']))

grouped_blocks = []
if raw_items:
@@ -515,8 +513,11 @@ def get_empty_data():
blocks = []
for grp in grouped_blocks:
eff_w, eff_d = grp['w'], grp['d']
            # 固定指示があればここで寸法確定
if grp['orient'] == "縦固定":
eff_w, eff_d = grp['d'], grp['w']
            elif grp['orient'] == "横固定":
                eff_w, eff_d = grp['w'], grp['d']

layers = max(1, int(PH // grp['h']))
full_stacks = int(grp['count'] // layers)
@@ -545,7 +546,8 @@ def get_empty_data():
'child': None, 'z': 0, 'p_id': grp['p_id'],
'prio': grp['prio'],
'orient': grp['orient'],
                    'orig_w': grp['w'], 'orig_d': grp['d']
                    'orig_w': grp['w'], 'orig_d': grp['d'],
                    'min_sub_id': min(stack_ids) # ソート安定用
})

if remainder > 0:
@@ -566,10 +568,13 @@ def get_empty_data():
'child': None, 'z': 0, 'p_id': grp['p_id'],
'prio': grp['prio'],
'orient': grp['orient'],
                    'orig_w': grp['w'], 'orig_d': grp['d']
                    'orig_w': grp['w'], 'orig_d': grp['d'],
                    'min_sub_id': min(stack_ids)
})

        blocks.sort(key=lambda x: (-x['prio'], -x['w']*x['d'], -x['h_total']))
        # ブロック配置順のソート: 優先度 -> 元の行番号 -> 箱の番号
        # これで「勝手に割り込む」のを防ぐ
        blocks.sort(key=lambda x: (-x['prio'], x['p_id'], x['min_sub_id']))

merged_indices = set()
for i in range(len(blocks)):
@@ -588,14 +593,16 @@ def get_empty_data():

if (limit_w >= top['w'] and limit_d >= top['d']) or (limit_w >= top['d'] and limit_d >= top['w']):
if not (limit_w >= top['w'] and limit_d >= top['d']):
                         if top['orient'] == "横固定": pass 
                         elif top['orient'] == "縦固定": pass
                         else: 
                         if top['orient'] == "自動":
                             # 自動なら回転して乗せる
final_top_w, final_top_d = top['d'], top['w']
can_stack = True
                         elif top['orient'] == "縦固定": pass
                         elif top['orient'] == "横固定": pass
else:
can_stack = True

                # 自動の場合、回転トライ
if not can_stack and top['orient'] == "自動":
rot_w, rot_d = top['d'], top['w']
if (limit_w >= rot_w and limit_d >= rot_d) or (limit_w >= rot_d and limit_d >= rot_w):
@@ -624,8 +631,10 @@ def get_empty_data():

try_orientations = []
if blk['orient'] == "自動":
                    try_orientations = [(blk['w'], blk['d']), (blk['d'], blk['w'])]
                    # 自動：まずは「元の向き(横)」を試す -> ダメなら「縦」
                    try_orientations = [(blk['orig_w'], blk['orig_d']), (blk['orig_d'], blk['orig_w'])]
else:
                    # 固定：今の向きだけ
try_orientations = [(blk['w'], blk['d'])]

best_fit = None
@@ -653,16 +662,19 @@ def get_empty_data():
if not placed:
fin_w, fin_d = blk['w'], blk['d']
if blk['orient'] == "自動":
                    if blk['w'] > PW and blk['d'] <= PW:
                        fin_w, fin_d = blk['d'], blk['w']
                    # 新規パレットでも「基本は横」
                    fin_w, fin_d = blk['orig_w'], blk['orig_d']
                    # ただし、幅が入らないなら回転
                    if fin_w > PW and fin_d <= PW:
                        fin_w, fin_d = blk['orig_d'], blk['orig_w']

blk['w'], blk['d'] = fin_w, fin_d
new_state = {'items': [blk], 'cur_g': w_total, 'cx': blk['w'], 'cy': 0, 'rh': blk['d']}
blk['x'] = 0; blk['y'] = 0; blk['z'] = 0; pallet_states.append(new_state)

st.session_state.results = [ps['items'] for ps in pallet_states]
st.session_state.params = {'PW':PW, 'PD':PD, 'PH':PH, 'MAX_W':MAX_W, 'OH':OH}
        st.session_state.input_products = items # 復活済み
        st.session_state.input_products = items 
st.session_state.calculated = True

# --- 結果表示 ---
