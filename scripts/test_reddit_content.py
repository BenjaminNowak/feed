#!/usr/bin/env python3
"""Test LLM analysis on Reddit-style content."""

from feed_aggregator.processing.llm_filter import LLMFilter


def main():
    # Simulate the content that was published (Reddit post with link)
    reddit_content = {
        "title": "Make Self-XSS Great Again",
        "content": (
            """<div><p>submitted by """
            """<a href="https://www.reddit.com/user/AlmondOffSec">/u/AlmondOffSec</a>"""
            """<br><a href="https://blog.slonser.info/posts/make-self-xss-great-again/">"""
            """[link]</a>"""
            """<a href="https://www.reddit.com/r/netsec/comments/1dz8k8z/make_selfxss_great_again/">"""
            """[comments]</a></p></div>"""
        ),
    }

    print("Testing Reddit-style content with updated prompts:")
    print(f"Title: {reddit_content['title']}")
    print(f"Content length: {len(reddit_content['content'])} characters")
    print(f"Content: {reddit_content['content']}")
    print()

    # Test with Tech category
    print("=== Tech Category Analysis ===")
    llm_filter_tech = LLMFilter(provider="ollama", category="Tech")
    result_tech = llm_filter_tech.analyze_item(reddit_content)

    print(f"Relevance Score: {result_tech['relevance_score']}")
    print(f"Summary: {result_tech['summary']}")
    print(f"Key Topics: {result_tech['key_topics']}")
    if result_tech.get("filtered_reason"):
        print(f"Filtered Reason: {result_tech['filtered_reason']}")
    print(f"Prompt Version: {result_tech['_analysis_metadata']['prompt_version']}")
    print(f"Category: {result_tech['_analysis_metadata']['category']}")
    print()

    # Test with Cyber category
    print("=== Cyber Category Analysis ===")
    llm_filter_cyber = LLMFilter(provider="ollama", category="Cyber")
    result_cyber = llm_filter_cyber.analyze_item(reddit_content)

    print(f"Relevance Score: {result_cyber['relevance_score']}")
    print(f"Summary: {result_cyber['summary']}")
    print(f"Key Topics: {result_cyber['key_topics']}")
    if result_cyber.get("filtered_reason"):
        print(f"Filtered Reason: {result_cyber['filtered_reason']}")
    print(f"Prompt Version: {result_cyber['_analysis_metadata']['prompt_version']}")
    print(f"Category: {result_cyber['_analysis_metadata']['category']}")


if __name__ == "__main__":
    main()
