import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer

BASE_URL = "http://localhost:5000/verify"  # swap for your real URL when deployed

def generate_qr(diamond_id: str, output_path: str = None):
    url = f"{BASE_URL}/{diamond_id}"
    output_path = output_path or f"qr_{diamond_id}.png"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color="#534AB7",   # DiamondChain purple
        back_color="white",
    )
    img.save(output_path)
    print(f"QR saved: {output_path}  →  {url}")
    return output_path

if __name__ == "__main__":
    generate_qr("DC-2025-BW-00441")
