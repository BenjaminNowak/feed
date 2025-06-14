# feed

This repository demonstrates a minimal GitHub Pages site that publishes an RSS feed and includes a Python feed aggregator that can fetch data from Feedly. The sample entry references DeepMind's AlphaEvolve project.

AlphaEvolve PDF: https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf
Blog post: https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
Repository: https://github.com/BenjaminNowak/feed

## Feed Aggregator Setup

### Quick Setup

Run the setup script to create a virtual environment and install dependencies:

```bash
./setup_env.sh
```

### Manual Setup

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

### Running the Example

#### Demo Mode (No API Token Required)

```bash
source venv/bin/activate
python scripts/example_fetch.py
```

This will run in demo mode and return sample data.

#### With Feedly API Access

Set your Feedly credentials as environment variables:

```bash
export FEEDLY_TOKEN='your_feedly_access_token'
export FEEDLY_USER='your_feedly_user_id'  # e.g., 808d013f-58fe-49e9-890e-53d4a5157874
source venv/bin/activate
python scripts/example_fetch.py
```

### Running Tests

```bash
source venv/bin/activate
python -m pytest tests/test_fetcher.py -v
```

## Viewing the RSS feed

Once GitHub Pages is enabled, navigate to `https://<username>.github.io/<repository>/feed.xml` (replace `<username>` and `<repository>` with your values) to see the RSS output. The site includes a basic `index.html` page that links to the feed.

## Enabling GitHub Pages

1. Open the repository on GitHub and go to **Settings**.
2. Select **Pages** from the left sidebar.
3. Under **Build and deployment**, choose the branch (e.g., `main`) and the folder (usually `/root` or `/docs`).
4. Click **Save**. GitHub will provide a link to your published site in a few moments.
