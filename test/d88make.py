#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# D88 floppy disk image creator
# Copyright 20260313a Hiroaki GOTO as GORRY
#

import sys
import os
import argparse
import struct

# -----------------------------------------------------------------------------
# D88 definitions
# -----------------------------------------------------------------------------

# D88 header size
D88_HEADER_SIZE = 688

# D88 track offset table size
D88_TRACK_OFFSET_TABLE_SIZE = 656

# D88 disk name size
D88_DISK_NAME_SIZE = 17

# -----------------------------------------------------------------------------
# D88 creator class
# -----------------------------------------------------------------------------

class D88Make:
    """
    D88 floppy disk image creator class
    """

    def __init__(self):
        """
        Constructor
        """
        self.args = None
        self.image_data = None
        self.track_offsets = [0] * 164

    def parse_args(self):
        """
        Parse command line arguments
        """
        parser = argparse.ArgumentParser(
            description="D88 floppy disk image creator",
            add_help=True,
        )

        parser.add_argument("output", help="Output D88 image file name")
        parser.add_argument("-a", "--name", default="DISK01", help="Disk name (max 16 chars)")
        parser.add_argument("-d", "--density", choices=["D", "DD", "HD"], default="D", help="Density (D, DD, HD)")
        parser.add_argument("-c", "--cylindar", type=int, default=40, help="Number of cylinders (1-100)")
        parser.add_argument("-s", "--side", type=int, choices=[1, 2], default=2, help="Number of sides (1 or 2)")
        parser.add_argument("-r", "--sector", type=int, default=16, help="Sectors per track (1-32)")
        parser.add_argument("-n", "--length", type=int, choices=[128, 256, 512, 1024], default=256, help="Sector length (128, 256, 512, 1024)")
        parser.add_argument("-i", "--image", help="Raw disk image file to embed")
        parser.add_argument("-b", "--double", action="store_true", help="Expand 2D image to 2DD")

        self.args = parser.parse_args()

    def get_geometry_from_image_size(self):
        """
        Get geometry from image size
        """
        if self.args.image:
            try:
                image_size = os.path.getsize(self.args.image)
                if self.args.double:
                    image_size *= 2
                
                geometries = {
                    327680:  (40, 16, 256,  2, "D"),
                    368640:  (40, 9,  512,  2, "D"),
                    655360:  (80, 16, 256,  2, "DD"),
                    737280:  (80, 9,  512,  2, "DD"),
                    1228800: (80, 15, 512,  2, "HD"),
                    1261568: (77, 8,  1024, 2, "HD"),
                    1474560: (80, 18, 512,  2, "HD"),
                }

                if image_size in geometries:
                    geo_cyl, geo_sec, geo_len, geo_sid, geo_den = geometries[image_size]
                    
                    # ユーザーが特定の値を指定していない場合にのみ、自動ジオメトリ設定を適用する。
                    if self.args.cylindar == 40:
                        self.args.cylindar = geo_cyl
                    if self.args.sector == 16:
                        self.args.sector = geo_sec
                    if self.args.length == 256:
                        self.args.length = geo_len
                    if self.args.side == 2:
                        self.args.side = geo_sid
                    if self.args.density == "D":
                        self.args.density = geo_den

            except FileNotFoundError:
                print(f"Error: Image file not found: {self.args.image}", file=sys.stderr)
                sys.exit(1)


    def validate_args(self):
        """
        Validate arguments
        """
        if len(self.args.name) > 16:
            print("Error: Disk name is too long (max 16 chars).", file=sys.stderr)
            sys.exit(1)
        if not (1 <= self.args.cylindar <= 100):
            print("Error: Number of cylinders must be between 1 and 100.", file=sys.stderr)
            sys.exit(1)
        if not (1 <= self.args.sector <= 32):
            print("Error: Sectors per track must be between 1 and 32.", file=sys.stderr)
            sys.exit(1)
        if self.args.side == 1 and self.args.density == "HD":
            print("Error: 1HD format is not supported.", file=sys.stderr)
            sys.exit(1)

    def print_geometry(self):
        """
        Print disk geometry
        """
        print("Disk Geometry:")
        print(f"  Name:      {self.args.name}")
        print(f"  Density:   {self.args.density}")
        print(f"  Cylinders: {self.args.cylindar}")
        print(f"  Sides:     {self.args.side}")
        print(f"  Sectors:   {self.args.sector}")
        print(f"  SecLen:    {self.args.length}")
        print(f"  2D->2DD:   {'Yes' if self.args.double else 'No'}")


    def run(self):
        """
        Main process
        """
        self.parse_args()
        self.get_geometry_from_image_size()
        self.validate_args()
        self.print_geometry()

        if self.args.image:
            try:
                with open(self.args.image, "rb") as f:
                    self.image_data = f.read()
            except FileNotFoundError:
                # get_geometry_from_image_size で既に処理されているが、フォールバックとして。
                print(f"Error: Image file not found: {self.args.image}", file=sys.stderr)
                sys.exit(1)


        try:
            with open(self.args.output, "wb") as f:
                # プレースホルダのヘッダを書き込む
                f.write(b'\x00' * D88_HEADER_SIZE)
                
                image_pos = 0
                total_sector_size = 0

                # トラックデータを書き込む
                for c in range(self.args.cylindar):
                    for h in range(self.args.side):
                        track_index = c * 2 + h
                        if track_index < len(self.track_offsets):
                            self.track_offsets[track_index] = f.tell()

                        header_c = c
                        if self.args.double:
                            header_c = c // 2

                        for r in range(1, self.args.sector + 1):
                            # セクタヘッダ
                            f.write(struct.pack('<B', header_c))  # シリンダ (C)
                            f.write(struct.pack('<B', h))  # ヘッド (H)
                            f.write(struct.pack('<B', r))  # レコード (R)
                            n_map = {128: 0, 256: 1, 512: 2, 1024: 3}
                            f.write(struct.pack('<B', n_map[self.args.length]))  # サイズ (N)
                            f.write(struct.pack('<H', self.args.sector)) # トラック内のセクタ数
                            density_map = {"D": 0x00, "DD": 0x00, "HD": 0x01}
                            f.write(struct.pack('<B', density_map[self.args.density])) # 密度
                            f.write(b'\x00')  # 削除フラグ
                            f.write(b'\x00')  # ステータス
                            f.write(b'\x00' * 5)  # 予約領域
                            f.write(struct.pack('<H', self.args.length)) # データサイズ

                            # セクタデータ
                            data_to_write = b'\x00' * self.args.length
                            if self.image_data:
                                read_pos = image_pos
                                if self.args.double:
                                    img_c = c // 2
                                    img_track_offset = (img_c * self.args.side + h) * self.args.sector * self.args.length
                                    img_sector_offset = (r - 1) * self.args.length
                                    read_pos = img_track_offset + img_sector_offset
                                
                                if read_pos < len(self.image_data):
                                    end_pos = read_pos + self.args.length
                                    chunk = self.image_data[read_pos:end_pos]
                                    data_to_write = chunk.ljust(self.args.length, b'\x00')
                                    if not self.args.double:
                                        image_pos = end_pos
                            
                            f.write(data_to_write)
                            total_sector_size += self.args.length

                # 合計ファイルサイズを取得
                disk_size = f.tell()

                # 最終的なヘッダを書き込むために先頭に戻る
                f.seek(0)

                # ディスク名
                f.write(self.args.name.encode('ascii').ljust(D88_DISK_NAME_SIZE, b'\x00'))
                
                # 予約領域
                f.write(b'\x00' * 9)
                
                # 書き込み禁止
                f.write(b'\x00')

                # ディスクタイプ
                type_map = {
                    (2, "D"): 0x00, (2, "DD"): 0x10, (2, "HD"): 0x20,
                    (1, "D"): 0x30, (1, "DD"): 0x40
                }
                disk_type = type_map.get((self.args.side, self.args.density), 0x00)
                f.write(struct.pack('<B', disk_type))

                # ディスクサイズ
                f.write(struct.pack('<I', disk_size))

                # トラックオフセットテーブル
                for offset in self.track_offsets:
                    f.write(struct.pack('<I', offset))

            print(f"\nSuccessfully created {self.args.output} ({disk_size} bytes).")

            if self.image_data:
                written_image_size = self.args.cylindar * self.args.side * self.args.sector * self.args.length
                if self.args.double:
                    # 2倍モードでは、ソースイメージと書き込まれたサイズの半分を比較する
                    written_image_size //= 2

                if len(self.image_data) != written_image_size:
                     print(f"Info: Input image size ({len(self.image_data)} bytes) does not match "
                           f"the logical disk size ({written_image_size} bytes).")


        except IOError as e:
            print(f"Error: File I/O error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
            sys.exit(1)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    d88 = D88Make()
    d88.run()