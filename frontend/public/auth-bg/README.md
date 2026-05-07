# Auth Background Images

This directory contains background images for the authentication pages (Login, Register, Force Password Change).

## 🚀 Fully Automatic Loading

**Just drop your images here - no code changes needed!**

The system automatically detects and loads ALL image files from this directory. Simply:
1. Add image files to `/frontend/public/auth-bg/`
2. Restart dev server or rebuild
3. Done! Images appear in rotation automatically ✨

### Supported Formats
- `.jpg` / `.jpeg`
- `.png`
- `.gif`
- `.webp`
- `.svg`

### Naming Convention (Optional)
Use kebab-case filenames for auto-generated titles:
- `city-walk.jpg` → Title: "City Walk"
- `tech-network.png` → Title: "Tech Network"
- `my-background.jpg` → Title: "My Background"

You can have ANY number of images - they'll all be included!

## Image Requirements

- **Resolution**: 1920x1080px or higher (Full HD)
- **Format**: JPG or PNG
- **File Size**: Optimize to <500KB for performance
- **Aspect Ratio**: 16:9 recommended

## Suggested Images

You can use any images you like. Here are some suggestions:

1. **Technology/Network** - Digital themes, circuit boards, network visualizations
2. **Nature/Landscape** - Mountains, oceans, forests, skies
3. **City/Cityscape** - Urban skylines, landmarks (e.g., HK, Shenzhen)
4. **Abstract** - Gradients, patterns, artistic designs
5. **Company Photos** - Office buildings, team photos (if appropriate)

## Where to Get Images

### Option 1: Free Stock Photo Sites
- [Unsplash](https://unsplash.com/) - High-quality free photos
- [Pexels](https://www.pexels.com/) - Free stock photos
- [Pixabay](https://pixabay.com/) - Free images and videos

### Option 2: Company Photos
Use official company/city photos if available (ensure you have rights to use them).

### Option 3: Generate with AI
Use AI image generation tools like Midjourney, DALL-E, or Stable Diffusion.

## Optimization Tips

Before deploying:
```bash
# Install image optimization tool
npm install -g imagemin-cli

# Optimize all images in this directory
imagemin *.{jpg,png} --out-dir=.
```

Or use online tools:
- [TinyPNG](https://tinypng.com/) - For PNG files
- [Squoosh](https://squoosh.app/) - Google's image optimizer

## Fallback

The first background is always an animated CSS gradient that requires no images. This ensures the auth pages look great even if:
- No images are added yet
- Images fail to load
- Deploying to intranet without images ready

## Deployment for Intranet

For intranet deployments without internet access:
1. Download all required images before deployment
2. Place them in `/frontend/public/auth-bg/` directory
3. Rebuild the application (`npm run build`)
4. The images will be served statically by the web server
5. No external dependencies required
6. No code changes needed - just add/remove files!

## File Structure

```
frontend/
├── public/
│   └── auth-bg/
│       ├── README.md              # This file
│       ├── tech-network.jpg       # Automatically loaded
│       ├── nature-mountain.jpg    # Automatically loaded
│       ├── city-walk.jpg          # Automatically loaded
│       ├── city-shenzhen.jpg      # Automatically loaded
│       └── your-image.png         # Just add it - auto detected!
└── src/
    └── components/
        └── auth/
            └── AuthBackground.vue # Auto-detects all images
```

## Adding/Removing Images

### ✅ To Add a New Image:
1. Copy image file to `/frontend/public/auth-bg/`
2. Restart dev server or rebuild production
3. That's it! Image appears automatically

**Example:**
```bash
# Just copy the file
cp ~/Downloads/beautiful-sunset.jpg frontend/public/auth-bg/

# Restart dev server
npm run dev
```

### ❌ To Remove an Image:
1. Delete the file from `/frontend/public/auth-bg/`
2. Restart dev server or rebuild
3. Done!

### 🔄 To Reorder Images:
Images rotate alphabetically by filename. Rename files to control order:
- `01-city.jpg` (shows first)
- `02-tech.jpg` (shows second)
- `03-nature.jpg` (shows third)

## Tips

- **Start small**: Begin with 2-3 images, add more as needed
- **Mix styles**: Combine different types (nature, city, abstract) for variety
- **Test loading**: Ensure images load quickly (<2s on slow connections)
- **Consistent quality**: Use similar resolution/quality across all images
- **Name clearly**: Use descriptive filenames for easy management
- **No config needed**: Never edit code to add/remove backgrounds!
