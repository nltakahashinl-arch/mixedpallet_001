import streamlit as st

# タイトル
st.title('📦 パレット積載数 シミュレーター')
st.write('段ボールのサイズとパレットの条件を入力して、積載数を計算します。')

# --- 1. 入力エリア ---
st.header('1. サイズ入力 (mm)')

col1, col2 = st.columns(2)

with col1:
    st.subheader('段ボール (貨物)')
    box_l = st.number_input('長さ (L)', value=300, step=10)
    box_w = st.number_input('幅 (W)', value=200, step=10)
    box_h = st.number_input('高さ (H)', value=150, step=10)

with col2:
    st.subheader('パレット・制限')
    pallet_l = st.number_input('パレット 長さ', value=1100, step=50)
    pallet_w = st.number_input('パレット 幅', value=1100, step=50)
    max_h = st.number_input('最大高さ (パレット込)', value=1500, step=50)
    pallet_base_h = st.number_input('パレット自体の高さ', value=150, step=10)

# --- 2. 計算ロジック ---
# 積める有効な高さ = 最大高さ - パレット自体の高さ
effective_h = max_h - pallet_base_h

if st.button('計算する'):
    # パターンA: そのまま置く (L方向にL、W方向にW)
    num_l_a = pallet_l // box_l  # 長さ方向に何個置けるか（割り算の整数部分）
    num_w_a = pallet_w // box_w  # 幅方向に何個置けるか
    layer_count_a = num_l_a * num_w_a # 1段あたりの個数

    # パターンB: 90度回転して置く (L方向にW、W方向にL)
    num_l_b = pallet_l // box_w
    num_w_b = pallet_w // box_l
    layer_count_b = num_l_b * num_w_b

    # 段数の計算 (高さ方向に何段積めるか)
    tiers = effective_h // box_h

    # --- 3. 結果表示 ---
    st.markdown('---')
    st.header('📊 計算結果')

    # 結果を見やすく表示
    c1, c2 = st.columns(2)
    
    with c1:
        st.info(f'**パターンA (並行積み)**')
        st.write(f'1段の個数: **{layer_count_a}** 個')
        st.write(f'({num_l_a}列 × {num_w_a}列)')
        st.metric(label="合計積載数", value=f"{layer_count_a * tiers} 個")

    with c2:
        st.success(f'**パターンB (回転積み)**')
        st.write(f'1段の個数: **{layer_count_b}** 個')
        st.write(f'({num_l_b}列 × {num_w_b}列)')
        st.metric(label="合計積載数", value=f"{layer_count_b * tiers} 個")

    st.write(f'積める段数: **{tiers}** 段 (有効高さ {effective_h}mm)')

    # どっちがお得かアドバイス
    if layer_count_a > layer_count_b:
        st.markdown('👉 **パターンA（そのまま）の方が多く積めます！**')
    elif layer_count_b > layer_count_a:
        st.markdown('👉 **パターンB（回転）の方が多く積めます！**')
    else:
        st.markdown('👉 **どちらも同じ数が積めます。**')
