# Multi-Category Feed Processing

This document describes the multi-category feed processing system that allows you to process different types of content with category-specific configurations and prompts.

## Overview

The system has been refactored to support multiple categories, each with their own:
- Quality thresholds
- LLM prompts tailored to the content type
- High-quality article targets
- Output feed files

## Configuration

### Categories Configuration

The main configuration is in `config/categories.yml`:

```yaml
categories:
  ML:
    name: "Machine Learning"
    description: "Machine Learning and AI content"
    feedly_category: "ML"
    prompts_file: "ml.yml"
    quality_threshold: 0.6
    high_quality_target: 10
    output_feed: "feed_ml.xml"
    
  Tech:
    name: "Technology"
    description: "General technology news and updates"
    feedly_category: "Tech"
    prompts_file: "tech.yml"
    quality_threshold: 0.7
    high_quality_target: 8
    output_feed: "feed_tech.xml"
    
  # ... more categories

global:
  default_fetch_count: 100
  default_provider: "ollama"
```

### Category-Specific Prompts

Each category has its own prompts file in `config/prompts/`:

- `config/prompts/ml.yml` - Machine Learning specific prompts
- `config/prompts/tech.yml` - Technology specific prompts
- `config/prompts/cyber.yml` - Cybersecurity specific prompts
- `config/prompts/programming.yml` - Programming specific prompts
- `config/prompts/culture.yml` - Tech culture specific prompts

Each prompts file contains LLM instructions tailored to evaluate content quality for that specific domain.

## Available Categories

The system currently supports these categories:

1. **ML** - Machine Learning and AI content
   - Quality threshold: 0.6
   - Target: 10 high-quality articles
   - Focus: Technical ML/AI content, research, implementations

2. **Tech** - General technology news
   - Quality threshold: 0.7
   - Target: 8 high-quality articles
   - Focus: Technology trends, product launches, technical analysis

3. **Cyber** - Cybersecurity content
   - Quality threshold: 0.65
   - Target: 12 high-quality articles
   - Focus: Security research, vulnerabilities, threat analysis

4. **Programming** - Programming and development
   - Quality threshold: 0.6
   - Target: 10 high-quality articles
   - Focus: Code tutorials, development practices, tools

5. **Culture** - Tech culture and current events
   - Quality threshold: 0.5
   - Target: 15 high-quality articles
   - Focus: Industry culture, politics, humor, geopolitical analysis

## Usage

### Processing a Single Category

```bash
# Process ML category
python scripts/process_category_runner.py ML

# Process with command line argument
python feed_aggregator/etl/process_category.py ML
```

### Processing Multiple Categories

```bash
# Process specific categories
python scripts/process_categories_runner.py ML Tech Cyber

# Process all configured categories
python scripts/process_categories_runner.py --all
```

### List Available Categories

```bash
python scripts/process_categories_runner.py --list
```

## Backward Compatibility

The original `process_category.py` script maintains backward compatibility:
- Running without arguments defaults to processing the "ML" category
- Existing tests continue to pass
- The original `scripts/process_category_runner.py` still works

## Adding New Categories

To add a new category:

1. **Add to categories.yml**:
   ```yaml
   NewCategory:
     name: "New Category Name"
     description: "Description of the category"
     feedly_category: "FeedlyCategoryName"
     prompts_file: "newcategory.yml"
     quality_threshold: 0.6
     high_quality_target: 10
     output_feed: "feed_newcategory.xml"
   ```

2. **Create prompts file** at `config/prompts/newcategory.yml`:
   ```yaml
   llm_filter:
     version: "1.0"
     system_prompt: |
       Your category-specific analysis instructions...
     user_prompt: |
       Title: {title}
       Content: {content}
       Analyze this content and return a JSON response.
     # Model configurations...
   ```

3. **Test the new category**:
   ```bash
   python scripts/process_categories_runner.py NewCategory
   ```

## Architecture

### Key Components

- **CategoryConfig**: Manages loading and accessing category configurations
- **LLMFilter**: Updated to use category-specific prompts
- **process_category.py**: Refactored to be generic and accept category parameters
- **process_categories_runner.py**: New script for batch processing multiple categories

### Configuration Flow

1. Load `config/categories.yml`
2. For each category, load category-specific prompts from `config/prompts/{category}.yml`
3. Initialize LLMFilter with category-specific prompts
4. Process articles using category-specific quality thresholds
5. Generate category-specific output feeds

## Testing

Run tests for the multi-category system:

```bash
# Test category configuration
pytest tests/test_category_config.py -v

# Test process category (includes backward compatibility)
pytest tests/test_process_category.py -v

# Run all tests
pytest tests/ -v
```

## Monitoring and Logs

Each category processing session includes:
- Category-specific quality thresholds in logs
- Progress tracking per category
- Success/failure reporting for batch operations
- MongoDB statistics per processing run

The system maintains separate tracking for each category while sharing the same MongoDB collections.
