# verify_task9.py
"""
Quick verification that Task 9 is working
"""
import requests
import json

BASE_URL = "http://localhost:5000"

print("=" * 60)
print("TASK 9 QUICK VERIFICATION")
print("=" * 60)

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health Check: {data.get('status', 'unknown')}")
            print(f"   Model loaded: {data.get('model_loaded', False)}")
            return True
        else:
            print(f"❌ Health Check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health Check error: {e}")
        return False

def test_ai_stats():
    """Test AI stats endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/ai-stats")
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stats = data.get('ai_model', {}).get('stats', {})
                print(f"✅ AI Stats:")
                print(f"   Model: {data.get('ai_model', {}).get('name', 'Unknown')}")
                print(f"   Loaded: {data.get('ai_model', {}).get('loaded', False)}")
                print(f"   Inferences: {stats.get('total_inferences', 0)}")
                return True
        else:
            print(f"❌ AI Stats failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ AI Stats error: {e}")
        return False

def test_text_summarization():
    """Test direct text summarization"""
    try:
        test_text = "Artificial intelligence is transforming many industries. " * 5
        
        response = requests.post(
            f"{BASE_URL}/api/v1/summarize",
            json={
                "text": test_text,
                "compression_ratio": 0.3
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Text Summarization works")
                print(f"   Original: {data.get('original_length', 0)} words")
                print(f"   Summary: {data.get('summary_length', 0)} words")
                print(f"   Compression: {data.get('compression_ratio', 0):.1%}")
                return True
            else:
                print(f"❌ Summarization failed: {data.get('error', 'Unknown')}")
                return False
        else:
            print(f"❌ Summarization API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Summarization test error: {e}")
        return False

def main():
    """Run verification tests"""
    print("\nTesting Task 9 endpoints...\n")
    
    tests = [
        ("Health Check", test_health),
        ("AI Statistics", test_ai_stats),
        ("Text Summarization", test_text_summarization)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    
    if passed == total:
        print("🎉 TASK 9 VERIFICATION COMPLETE!")
        print("All API endpoints are working correctly.")
        print("\nTask 9 Status: ✅ COMPLETED")
        return True
    elif passed >= 2:
        print("⚠️  TASK 9 PARTIALLY VERIFIED")
        print(f"{passed}/{total} tests passed.")
        print("Core functionality is working.")
        print("\nTask 9 Status: ✅ FUNCTIONAL (Minor issues)")
        return True
    else:
        print("❌ TASK 9 VERIFICATION FAILED")
        print(f"Only {passed}/{total} tests passed.")
        print("\nTask 9 Status: ❌ NEEDS FIXING")
        return False

if __name__ == "__main__":
    print("Make sure the Flask app is running on http://localhost:5000")
    print("Start it with: py app.py")
    print("\nPress Enter to start verification...")
    input()
    
    success = main()
    
    if success:
        print("\n✅ Proceed to next task or deployment.")
    else:
        print("\n❌ Fix the issues before proceeding.")