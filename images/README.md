# Images Directory

## Recommended Image Sizes

### Project Screenshots
- **Width**: 1200px
- **Height**: 800px
- **Format**: JPG or PNG
- **Size**: Keep under 500KB for fast loading

### File Naming
Use descriptive names:
- `project1-dashboard.jpg`
- `ecommerce-homepage.png`
- `mobile-app-login.jpg`

## How to Add Images
1. **Save your images** in this folder
2. **Update the HTML** in `index.html`:

```html
<!-- Replace the placeholder div -->
<div class="project-image">
    <img src="images/your-project-screenshot.jpg" alt="Project Name" style="width: 100%; height: 100%; object-fit: cover;">
</div>
```

## Image Optimization Tips

### Quick Optimization Tools:
- **Online**: TinyPNG, ImageOptim, Squoosh
- **Desktop**: ImageOptim (Mac), PngOptimizer (Windows)
- **CLI**: ImageMagick, Sharp

## Example Structure
```
images/
├── project1-homepage.jpg
├── project1-dashboard.png
├── project2-mobile.jpg
├── project3-admin.png
└── profile-photo.jpg
```
