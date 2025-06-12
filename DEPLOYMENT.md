# PyPI Deployment Setup

This repository now includes automated deployment to PyPI and TestPyPI using GitHub Actions.

## 🔧 Setup Required

### 1. Create PyPI API Tokens

You'll need to create API tokens for both TestPyPI and PyPI:

#### TestPyPI Token
1. Go to [TestPyPI Account Settings](https://test.pypi.org/manage/account/)
2. Scroll to "API tokens" section
3. Click "Add API token"
4. Name: `crawl4ai-mcp-testpypi`
5. Scope: "Entire account" (or specific to your project if it exists)
6. Copy the token (starts with `pypi-...`)

#### PyPI Token
1. Go to [PyPI Account Settings](https://pypi.org/manage/account/)
2. Scroll to "API tokens" section  
3. Click "Add API token"
4. Name: `crawl4ai-mcp-pypi`
5. Scope: "Entire account" (or specific to your project after first upload)
6. Copy the token (starts with `pypi-...`)

### 2. Add Secrets to GitHub Repository

1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"
3. Add the following repository secrets:
   - `TEST_PYPI_TOKEN`: Your TestPyPI API token
   - `PYPI_TOKEN`: Your PyPI API token

### 3. Set up GitHub Environments (Optional but Recommended)

For better security and deployment tracking:

1. Go to repository "Settings" → "Environments"
2. Create two environments:
   - `testpypi`: For TestPyPI deployments
   - `pypi`: For production PyPI deployments
3. For each environment, optionally add:
   - **Protection rules**: Require manual approval for deployments
   - **Environment secrets**: Move your API tokens here instead of repository secrets

## 🚀 How to Deploy

### Automatic Deployment (Recommended)

The workflow automatically triggers on GitHub releases:

1. **TestPyPI**: Deploys on any release creation (draft or published)
2. **PyPI**: Deploys only on published releases

#### Creating a Release

```bash
# Create and push a new tag
git tag v0.1.1
git push origin v0.1.1

# Then create a release on GitHub:
# 1. Go to repository → Releases → "Create a new release"
# 2. Choose your tag (v0.1.1)
# 3. Write release notes
# 4. Click "Publish release" for PyPI deployment
# 5. Or "Save draft" for TestPyPI only
```

### Manual Deployment

You can also trigger deployments manually:

1. Go to "Actions" → "Deploy to PyPI"
2. Click "Run workflow"
3. Choose deployment target:
   - `testpypi`: Deploy to TestPyPI for testing
   - `pypi`: Deploy to production PyPI

## 📦 Deployment Process

The workflow performs these steps:

1. **Build**: Creates wheel and source distributions
2. **Validate**: Checks package integrity and version consistency
3. **Deploy**: Uploads to TestPyPI or PyPI
4. **Test**: Verifies installation from the deployed package
5. **Track**: Creates GitHub deployment records

## 🔍 Version Management

The workflow automatically:
- Extracts version from `pyproject.toml`
- Validates version consistency with git tags (for releases)
- Uses semantic versioning

To bump version:
```bash
# Edit pyproject.toml
sed -i 's/version = "0.1.0"/version = "0.1.1"/' pyproject.toml

# Commit changes
git add pyproject.toml
git commit -m "Bump version to 0.1.1"
git push
```

## 🧪 Testing Your Package

After deployment to TestPyPI, test installation:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    crawl4ai-mcp

# Test basic functionality
python -c "import crawl4ai_mcp; print('✅ Import successful')"

# Test CLI
mcp-crawl4ai-rag --help
```

## 📊 Monitoring Deployments

Track your deployments:
- **Actions tab**: View workflow runs and logs
- **Environments**: See deployment history (if using environments)
- **Releases**: Link releases to deployments

## 🛡️ Security Best Practices

1. **Use environment secrets** instead of repository secrets
2. **Enable deployment protection rules** for production
3. **Review deployment logs** for any issues
4. **Rotate API tokens** periodically
5. **Use scoped tokens** when possible (project-specific)

## 🔧 Troubleshooting

### Common Issues

1. **Version conflicts**: Ensure `pyproject.toml` version matches git tag
2. **Token issues**: Verify tokens are valid and have correct permissions
3. **Package exists**: PyPI doesn't allow re-uploading same version
4. **Dependencies**: TestPyPI may have dependency resolution issues

### Workflow Debugging

Check the Actions tab for detailed logs. The workflow provides verbose output for each step.

### Re-deployment

If you need to re-deploy the same version:
1. Delete the release and tag
2. Update the version in `pyproject.toml`
3. Create a new release

## 📝 Next Steps

1. Set up your API tokens and secrets
2. Test with a manual deployment to TestPyPI
3. Create your first release
4. Monitor the deployment process
5. Install and test your package

Happy deploying! 🎉
