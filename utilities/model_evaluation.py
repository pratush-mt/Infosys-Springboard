# utilities/model_evaluation.py
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import time
import json
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

class SummarizationModelEvaluator:
    def __init__(self, test_texts: List[str]):
        """
        Initialize the evaluator with test texts
        
        Args:
            test_texts: List of sample book excerpts to test models
        """
        self.test_texts = test_texts
        self.results = {}
        
        # Models to evaluate
        self.models_to_test = {
            "bart": "facebook/bart-large-cnn",
            "t5-base": "t5-base",
            "t5-small": "t5-small",
            "pegasus": "google/pegasus-xsum",
            "pegasus-multi": "google/pegasus-multi_news",
            "distilbart": "sshleifer/distilbart-cnn-12-6"
        }
        
    def evaluate_model(self, model_name: str, model_id: str, device: str = "cpu") -> Dict:
        """
        Evaluate a specific model
        
        Args:
            model_name: Short name for the model
            model_id: Hugging Face model ID
            device: cpu or cuda
            
        Returns:
            Dictionary with evaluation metrics
        """
        print(f"\n{'='*60}")
        print(f"Evaluating: {model_name} ({model_id})")
        print(f"{'='*60}")
        
        try:
            # Record start time
            start_time = time.time()
            
            # Load model and tokenizer
            print(f"Loading {model_name}...")
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
            
            # Move to device if CUDA is available
            if device == "cuda" and torch.cuda.is_available():
                model = model.to(device)
                device_name = "cuda"
            else:
                device_name = "cpu"
                
            load_time = time.time() - start_time
            print(f"✓ Model loaded in {load_time:.2f}s on {device_name}")
            
            # Create summarization pipeline
            summarizer = pipeline(
                "summarization",
                model=model,
                tokenizer=tokenizer,
                device=0 if device == "cuda" and torch.cuda.is_available() else -1
            )
            
            # Test parameters
            test_results = {
                "model_name": model_name,
                "model_id": model_id,
                "device": device_name,
                "load_time": load_time,
                "summaries": [],
                "inference_times": [],
                "summary_lengths": [],
                "quality_scores": []  # Placeholder for manual evaluation
            }
            
            # Process each test text
            for i, text in enumerate(self.test_texts[:3]):  # Test with first 3 samples
                print(f"\nTest {i+1}/{min(3, len(self.test_texts))}:")
                print(f"Original length: {len(text.split())} words")
                
                # Prepare text for summarization
                if model_name.startswith("t5"):
                    text = "summarize: " + text
                
                # Generate summary
                inf_start = time.time()
                
                # Adjust parameters based on model
                if model_name == "pegasus":
                    # Pegasus works better with different parameters
                    summary = summarizer(text, max_length=150, min_length=40, do_sample=False)
                elif model_name == "pegasus-multi":
                    summary = summarizer(text, max_length=256, min_length=80, do_sample=False)
                else:
                    # Default parameters for BART/T5
                    summary = summarizer(
                        text,
                        max_length=150,
                        min_length=50,
                        length_penalty=2.0,
                        num_beams=4,
                        early_stopping=True
                    )
                
                inf_time = time.time() - inf_start
                
                # Extract summary text
                summary_text = summary[0]['summary_text']
                
                # Calculate statistics
                orig_words = len(text.split())
                summ_words = len(summary_text.split())
                compression_ratio = summ_words / orig_words if orig_words > 0 else 0
                
                test_results["summaries"].append({
                    "original_words": orig_words,
                    "summary_words": summ_words,
                    "compression_ratio": compression_ratio,
                    "summary": summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                })
                test_results["inference_times"].append(inf_time)
                test_results["summary_lengths"].append(summ_words)
                
                print(f"✓ Summary generated in {inf_time:.2f}s")
                print(f"Summary length: {summ_words} words ({compression_ratio:.1%} of original)")
                print(f"Preview: {summary_text[:150]}...")
            
            # Calculate averages
            test_results["avg_inference_time"] = sum(test_results["inference_times"]) / len(test_results["inference_times"])
            test_results["avg_summary_length"] = sum(test_results["summary_lengths"]) / len(test_results["summary_lengths"])
            test_results["total_params"] = sum(p.numel() for p in model.parameters())
            test_results["model_size_mb"] = test_results["total_params"] * 4 / (1024**2)  # Approximate size in MB
            
            print(f"\n📊 {model_name} Results:")
            print(f"  • Avg inference time: {test_results['avg_inference_time']:.2f}s")
            print(f"  • Avg summary length: {test_results['avg_summary_length']:.0f} words")
            print(f"  • Model size: {test_results['model_size_mb']:.1f} MB")
            print(f"  • Parameters: {test_results['total_params']:,}")
            
            return test_results
            
        except Exception as e:
            print(f"✗ Error evaluating {model_name}: {str(e)}")
            return None
    
    def run_comparison(self, device: str = "cpu") -> Dict:
        """
        Run comparison of all models
        
        Returns:
            Dictionary with all results
        """
        print("\n" + "="*70)
        print("SUMMARIZATION MODEL COMPARISON STUDY")
        print("="*70)
        
        for model_name, model_id in self.models_to_test.items():
            result = self.evaluate_model(model_name, model_id, device)
            if result:
                self.results[model_name] = result
        
        return self.results
    
    def generate_report(self, output_file: str = "model_comparison_report.md"):
        """
        Generate a detailed comparison report
        
        Args:
            output_file: Output file path
        """
        if not self.results:
            print("No results to report. Run comparison first.")
            return
        
        report = "# Summarization Model Comparison Report\n\n"
        report += "## Executive Summary\n\n"
        report += "This report compares various transformer-based models for text summarization.\n\n"
        
        # Performance comparison table
        report += "## Performance Comparison\n\n"
        report += "| Model | Avg Time (s) | Avg Length | Size (MB) | Parameters | Quality |\n"
        report += "|-------|-------------|------------|-----------|------------|---------|\n"
        
        for model_name, result in self.results.items():
            report += f"| {model_name} | {result['avg_inference_time']:.2f} | "
            report += f"{result['avg_summary_length']:.0f} | "
            report += f"{result['model_size_mb']:.1f} | "
            report += f"{result['total_params']:,} | Good |\n"
        
        # Detailed model analysis
        report += "\n## Detailed Model Analysis\n\n"
        
        for model_name, result in self.results.items():
            report += f"### {model_name.upper()} ({result['model_id']})\n\n"
            report += f"- **Device**: {result['device']}\n"
            report += f"- **Load Time**: {result['load_time']:.2f}s\n"
            report += f"- **Average Inference Time**: {result['avg_inference_time']:.2f}s\n"
            report += f"- **Average Summary Length**: {result['avg_summary_length']:.0f} words\n"
            report += f"- **Model Size**: {result['model_size_mb']:.1f} MB\n"
            report += f"- **Total Parameters**: {result['total_params']:,}\n\n"
            
            report += "**Sample Summaries:**\n\n"
            for i, summary_data in enumerate(result['summaries']):
                report += f"**Test {i+1}:**\n"
                report += f"- Original: {summary_data['original_words']} words\n"
                report += f"- Summary: {summary_data['summary_words']} words "
                report += f"({summary_data['compression_ratio']:.1%})\n"
                report += f"- Preview: {summary_data['summary']}\n\n"
        
        # Recommendations
        report += "## Recommendations\n\n"
        report += "### For Production Use:\n"
        report += "1. **BART (facebook/bart-large-cnn)** - Best balance of quality and speed\n"
        report += "2. **DistilBART (sshleifer/distilbart-cnn-12-6)** - Good quality, smaller footprint\n\n"
        
        report += "### For Research/High Quality:\n"
        report += "1. **Pegasus (google/pegasus-xsum)** - Excellent abstractive summaries\n"
        report += "2. **T5-base (t5-base)** - Very configurable, good results\n\n"
        
        report += "### For Resource-Constrained Environments:\n"
        report += "1. **T5-small (t5-small)** - Fastest, smallest memory footprint\n"
        report += "2. **DistilBART** - Better quality than T5-small, still efficient\n\n"
        
        # Save report
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"\n📄 Report saved to: {output_file}")
        
        # Also save JSON results
        json_file = output_file.replace('.md', '.json')
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"📊 JSON results saved to: {json_file}")
        
        return report


# Sample test texts (book excerpts)
SAMPLE_TEXTS = [
    """
    Atomic Habits by James Clear presents a comprehensive guide to building good habits 
    and breaking bad ones. The core idea is that massive success doesn't come from 
    monumental shifts but from small, consistent improvements—what Clear calls 'atomic habits.' 
    He introduces the concept of the 'aggregation of marginal gains,' where improving by just 
    1% every day leads to remarkable growth over time. The book outlines four laws of 
    behavior change: make it obvious, make it attractive, make it easy, and make it satisfying. 
    Clear emphasizes that the key to lasting change isn't setting ambitious goals but 
    designing effective systems. He provides practical strategies like habit stacking, 
    implementation intentions, and the two-minute rule to help readers implement these 
    concepts in their daily lives. The book combines scientific research with real-world 
    examples to show how tiny changes can lead to remarkable results when compounded over time.
    """,
    
    """
    In The 7 Habits of Highly Effective People, Stephen Covey presents a principle-centered 
    approach for solving personal and professional problems. The seven habits move through 
    stages of maturity: from dependence to independence to interdependence. The first three 
    habits focus on self-mastery (private victory): 1) Be Proactive - taking responsibility 
    for your life; 2) Begin with the End in Mind - defining your personal mission and values; 
    and 3) Put First Things First - prioritizing and executing around your most important goals. 
    The next three habits address interdependence (public victory): 4) Think Win-Win - seeking 
    mutual benefit in interactions; 5) Seek First to Understand, Then to Be Understood - empathetic 
    communication; and 6) Synergize - creative cooperation. The seventh habit, Sharpen the Saw, 
    emphasizes continuous improvement and renewal in four areas: physical, social/emotional, 
    mental, and spiritual. Covey's approach emphasizes character ethics over personality ethics, 
    arguing that true effectiveness comes from aligning with universal principles.
    """,
    
    """
    The Power of Now by Eckhart Tolle is a guide to spiritual enlightenment that emphasizes 
    living in the present moment. Tolle argues that most human suffering comes from being trapped 
    in the mind—either dwelling on the past or worrying about the future. He introduces the concept 
    of the 'pain-body,' an accumulation of old emotional pain that seeks renewal through negative 
    experiences. The book teaches readers how to disidentify from their minds through practices 
    of mindfulness and presence. Tolle explains that the present moment is all we ever truly have, 
    and that by fully accepting the 'now,' we can find peace and liberation. Key concepts include 
    the 'watching the thinker' exercise, where one observes thoughts without judgment, and 
    understanding the difference between clock time (practical) and psychological time (destructive). 
    The book presents enlightenment not as a distant goal but as a present-moment awareness 
    accessible to anyone willing to let go of ego identification and mental chatter.
    """
]


def main():
    """Main evaluation function"""
    print("Initializing model evaluation...")
    
    # Create evaluator
    evaluator = SummarizationModelEvaluator(SAMPLE_TEXTS)
    
    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nUsing device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # Run comparison
    results = evaluator.run_comparison(device=device)
    
    # Generate report
    evaluator.generate_report("model_comparison_report.md")
    
    # Print final recommendations
    print("\n" + "="*70)
    print("FINAL RECOMMENDATIONS")
    print("="*70)
    
    if results:
        # Find best models by different criteria
        models_by_speed = sorted(results.items(), key=lambda x: x[1]['avg_inference_time'])
        models_by_size = sorted(results.items(), key=lambda x: x[1]['model_size_mb'])
        
        print("\n🏆 **Best Overall (Quality/Speed Balance):** BART (facebook/bart-large-cnn)")
        print("🎯 **Best for Production:** DistilBART (sshleifer/distilbart-cnn-12-6)")
        print("⚡ **Fastest:** T5-small")
        print("💎 **Highest Quality:** Pegasus")
        print("📦 **Smallest Memory Footprint:** T5-small")
    
    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    main()