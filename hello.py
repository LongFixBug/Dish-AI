import asyncio

async def tra_cuu_dinh_duong(name):
    print(f"Bắt đầu tra cứu {name}...")
    await asyncio.sleep(1)

    return f"{name}: ... kcal"

# async def kho_thit():
#     print("bat dau kho thit...")
#     await asyncio.sleep(3)
#     print("thit kho xong")
#     return "thit"

async def main():
    cac_ket_qua = await asyncio.gather(
        tra_cuu_dinh_duong("thit bo"),
        tra_cuu_dinh_duong("bun"),
        tra_cuu_dinh_duong("rau thơm"),
        )
    print(f"kết quả: {cac_ket_qua}")

asyncio.run(main())