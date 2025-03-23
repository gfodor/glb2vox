#!/bin/bash

# Check if a file path was provided
if [ $# -ne 1 ]; then
  echo "Usage: $0 /path/to/model.glb"
  exit 1
fi

# Get the input file and extract base name without extension
INPUT_FILE="$1"
BASENAME=$(basename "$INPUT_FILE" .glb)
DIRNAME=$(dirname "$INPUT_FILE")
WORKING_DIR="$DIRNAME"

# Make sure input file exists and is a GLB file
if [ ! -f "$INPUT_FILE" ] || [[ "$INPUT_FILE" != *.glb ]]; then
  echo "Error: Input file must be a valid .glb file"
  exit 1
fi

cd "$WORKING_DIR"

echo "Extracting textures from $BASENAME.glb..."
assimp extract "$BASENAME.glb" textures

echo "Exporting to OBJ format..."
assimp export "$BASENAME.glb" "${BASENAME}_with_textures.obj" -ptv

echo "Fixing texture references in MTL file..."
sed -i '' -e 's/map_Kd \*0/map_Kd textures_img0.png/g' "${BASENAME}_with_textures.mtl"

echo "Converting to VOX format..."
wine ./poly2vox.exe /v96 /t "${BASENAME}_with_textures.mtl" "${BASENAME}_with_textures.obj" "$BASENAME.vox"

echo "Cleaning up intermediate files..."
rm -f "${BASENAME}_with_textures.obj" "${BASENAME}_with_textures.mtl" textures_img*.png

echo "Conversion complete: $BASENAME.vox"