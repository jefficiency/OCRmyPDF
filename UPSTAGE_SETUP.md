# Upstage OCR Setup Guide

## Environment Configuration with .env File

### 1. Create .env File

Create a `.env` file in the project root (same directory as `pyproject.toml`):

```bash
# Navigate to project root
cd /path/to/OCRmyPDF

# Create .env file
touch .env
```

### 2. Configure Environment Variables

Edit the `.env` file with your configuration:

```bash
# Required: Upstage API Key
UPSTAGE_API_KEY=your_actual_api_key_here

# Optional: Override default endpoint
# UPSTAGE_ENDPOINT=https://api.upstage.ai/v1/document-digitization

# Optional: Override default timeout (seconds)
# UPSTAGE_TIMEOUT=180.0
```

### 3. Install Dependencies

Install OCRmyPDF with Upstage support:

```bash
# Install OCRmyPDF with Upstage dependencies
pip install ocrmypdf[upstage]

# Or install dependencies manually
pip install python-dotenv requests
```

The plugin works without python-dotenv, but installing it enables automatic .env file loading.

### 4. Usage Examples

#### Using Environment Variables Only
```bash
# Set in .env file or export directly
export UPSTAGE_API_KEY=your_key_here
ocrmypdf --ocr-engine upstage input.pdf output.pdf
```

#### Using Command Line Options
```bash
ocrmypdf --ocr-engine upstage --upstage-api-key your_key_here input.pdf output.pdf
```

#### Mixed Configuration
```bash
# API key from .env, custom endpoint from command line
ocrmypdf --ocr-engine upstage --upstage-endpoint https://custom.endpoint.com input.pdf output.pdf
```

## Configuration Priority

The plugin resolves configuration in this order (highest to lowest priority):

1. **Command line arguments** (`--upstage-api-key`, `--upstage-endpoint`, etc.)
2. **Environment variables** (`UPSTAGE_API_KEY`, `UPSTAGE_ENDPOINT`, etc.)
3. **Default values**

## Security Notes

### .env File Security
- **Never commit .env files to version control**
- Add `.env` to your `.gitignore` file
- Use restrictive file permissions: `chmod 600 .env`

### API Key Management
- Keep API keys secure and rotate them regularly
- Use different keys for development and production
- Consider using a secrets management service for production deployments

## Troubleshooting

### Common Issues

1. **"Upstage API key is required" Error**
   - Check that `UPSTAGE_API_KEY` is set in .env or passed via command line
   - Verify the .env file is in the correct location (project root)
   - Ensure python-dotenv is installed for automatic .env loading

2. **"python-dotenv not available" Warning**
   - Install python-dotenv: `pip install python-dotenv`
   - Or set environment variables manually: `export UPSTAGE_API_KEY=your_key`

3. **Invalid Endpoint Error**
   - Ensure the endpoint starts with `http://` or `https://`
   - Check for typos in the URL

### Debug Mode

Enable debug logging to see environment variable loading:

```bash
ocrmypdf --verbose --ocr-engine upstage input.pdf output.pdf
```

Look for debug messages like:
- `Loaded environment variables from /path/to/.env`
- `Environment variables loaded from .env: Yes`

## Example .env Template

```bash
# Copy this template to .env and fill in your values

# Required Configuration
UPSTAGE_API_KEY=your_upstage_api_key_here

# Optional Configuration (uncomment to override defaults)
# UPSTAGE_ENDPOINT=https://api.upstage.ai/v1/document-digitization
# UPSTAGE_TIMEOUT=180.0
# UPSTAGE_MODEL=ocr

# Development/Testing Configuration
# UPSTAGE_DEBUG=true
# UPSTAGE_RATE_LIMIT=1.0
```
