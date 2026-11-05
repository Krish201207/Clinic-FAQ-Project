#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

// Runtime pipeline:
// input question -> Embedding.vec sentence vector -> trained softmax classifier
// -> if ROUTINE, cosine-search real FAQ questions -> return attached answer.
// Uses standard C++ only. It does NOT train weights; train them separately.

const string EMBEDDING_FILE = "Embeddings.vec";
const string WEIGHTS_FILE = "classifier_weights.txt";

const int ROUTINE = 0;
const int SENSITIVE = 1;
const int UNSUPPORTED = 2;
const int CLASS_COUNT = 3;
const string LABELS[CLASS_COUNT] = {"ROUTINE", "SENSITIVE", "UNSUPPORTED"};

unordered_map<string, vector<double>> wordVectors;
int embeddingVocab = 0;
int DIM = 0;

vector<vector<double>> W;
vector<double> bias;

string lowerCopy(string s) {
    for (char &c : s)
        c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    return s;
}

string normalize(string s) {
    for (char &c : s) {
        unsigned char ch = static_cast<unsigned char>(c);
        if (!isalnum(ch) && c != '\'') c = ' ';
        else c = static_cast<char>(tolower(ch));
    }
    return s;
}

vector<string> tokenize(const string &text) {
    istringstream in(normalize(text));
    vector<string> tokens;
    string token;
    while (in >> token) tokens.push_back(token);
    return tokens;
}

bool loadEmbeddingHeader() {
    ifstream in(EMBEDDING_FILE);
    if (!in) {
        cerr << "ERROR: Cannot open " << EMBEDDING_FILE << ".\n"
             << "Put your pretrained vector file beside ClinicAssistant.exe.\n";
        return false;
    }
    if (!(in >> embeddingVocab >> DIM) || embeddingVocab <= 0 || DIM <= 0) {
        cerr << "ERROR: Invalid .vec header. Expected: vocabulary_size dimensions.\n";
        return false;
    }
    cout << "Embedding dimensions: " << DIM << "\n";
    return true;
}

bool loadClassifier() {
    ifstream in(WEIGHTS_FILE);
    if (!in) {
        cerr << "ERROR: Cannot open " << WEIGHTS_FILE << ". Train the classifier first.\n";
        return false;
    }
    int classes = 0, modelDim = 0;
    if (!(in >> classes >> modelDim) || classes != CLASS_COUNT || modelDim != DIM) {
        cerr << "ERROR: Classifier weight dimensions do not match Embedding.vec.\n";
        cerr << "Expected " << CLASS_COUNT << " classes and " << DIM
             << " dimensions, but model reports " << classes << " and " << modelDim << ".\n";
        return false;
    }

    W.assign(CLASS_COUNT, vector<double>(DIM));
    bias.assign(CLASS_COUNT, 0.0);
    for (int c = 0; c < CLASS_COUNT; ++c) {
        if (!(in >> bias[c])) {
            cerr << "ERROR: Invalid bias in " << WEIGHTS_FILE << ".\n";
            return false;
        }
        for (int j = 0; j < DIM; ++j) {
            if (!(in >> W[c][j])) {
                cerr << "ERROR: Incomplete weights in " << WEIGHTS_FILE << ".\n";
                return false;
            }
        }
    }
    cout << "Loaded trained classifier weights.\n";
    return true;
}

void loadRequestedWords(const unordered_set<string> &requested) {
    unordered_set<string> missing;
    for (const string &w : requested)
        if (!wordVectors.count(w)) missing.insert(w);
    if (missing.empty()) return;

    ifstream in(EMBEDDING_FILE);
    int vocab = 0, dim = 0;
    if (!(in >> vocab >> dim)) return;
    string line;
    getline(in, line); // consume the rest of header line

    // Read each row as a complete line, because FastText vectors can contain
    // punctuation tokens and each row contains one word plus DIM numbers.
    while (!missing.empty() && getline(in, line)) {
        istringstream row(line);
        string word;
        if (!(row >> word) || !missing.count(word)) continue;

        vector<double> v(DIM);
        bool ok = true;
        for (int j = 0; j < DIM; ++j) {
            if (!(row >> v[j])) { ok = false; break; }
        }
        if (ok) {
            wordVectors.emplace(word, move(v));
            missing.erase(word);
        }
    }
}

vector<double> makeSentenceVector(const string &text, int &known, int &total) {
    vector<double> x(DIM, 0.0);
    vector<string> words = tokenize(text);
    known = 0;
    total = static_cast<int>(words.size());

    for (const string &word : words) {
        auto it = wordVectors.find(word);
        if (it == wordVectors.end()) continue;
        for (int j = 0; j < DIM; ++j) x[j] += it->second[j];
        ++known;
    }

    if (known > 0)
        for (double &v : x) v /= known;

    // Must match training preprocessing: L2-normalize the mean vector.
    double norm = 0.0;
    for (double v : x) norm += v * v;
    norm = sqrt(norm);
    if (norm > 1e-12)
        for (double &v : x) v /= norm;

    return x;
}

vector<double> softmax(const vector<double> &logits) {
    double maxLogit = *max_element(logits.begin(), logits.end());
    vector<double> p(logits.size());
    double sum = 0.0;
    for (size_t i = 0; i < logits.size(); ++i) {
        p[i] = exp(logits[i] - maxLogit);
        sum += p[i];
    }
    if (sum > 0.0)
        for (double &v : p) v /= sum;
    return p;
}

int classify(const vector<double> &x, vector<double> &probabilities) {
    vector<double> logits(CLASS_COUNT, 0.0);
    for (int c = 0; c < CLASS_COUNT; ++c) {
        logits[c] = bias[c];
        for (int j = 0; j < DIM; ++j)
            logits[c] += W[c][j] * x[j];
    }
    probabilities = softmax(logits);
    return static_cast<int>(max_element(probabilities.begin(), probabilities.end())
                            - probabilities.begin());
}

bool emergencyOverride(const string &query) {
    // Conservative safety override; classifier mistakes must not suppress obvious emergencies.
    const vector<string> phrases = {
        "severe chest pain", "not breathing", "turned blue",
        "difficulty breathing", "pregnant and bleeding",
        "want to end my life", "kill myself", "immediate danger"
    };
    string text = " " + normalize(query) + " ";
    for (const string &phrase : phrases) {
        string needle = " " + normalize(phrase) + " ";
        if (text.find(needle) != string::npos) return true;
    }
    return false;
}

int main() {
    cout << "=== Community Clinic FAQ Assistant ===\n";
    cout << "Pipeline: question -> vector -> trained classification -> routine questions sent to Flask/Gemini FAQ context\n\n";

    if (!loadEmbeddingHeader() || !loadClassifier()) return 1;

    cout << "FAQ retrieval is handled by the Python/Gemini backend.\n";
    cout << "Type 'exit' to quit.\n\n";

    string query;
    while (true) {
        cout << "You: ";
        if (!getline(cin, query)) break;
        if (lowerCopy(query) == "exit" || lowerCopy(query) == "quit") break;
        if (tokenize(query).empty()) {
            cout << "Assistant: Please enter a question.\n\n";
            continue;
        }

        unordered_set<string> queryWords;
        for (const string &w : tokenize(query)) queryWords.insert(w);
        loadRequestedWords(queryWords);

        // 1. Vectorize input.
        int known = 0, total = 0;
        vector<double> qVec = makeSentenceVector(query, known, total);
        cout << "\nVector coverage: " << known << "/" << total << " words.\n";
        // If no words are in the embedding vocabulary, the classifier cannot
        // make a valid prediction. Forward the question to Flask/Gemini as
        // UNSUPPORTED instead of rejecting it. Obvious emergencies stay blocked.
        vector<double> probs(CLASS_COUNT, 0.0);
        int category = UNSUPPORTED;

        if (known == 0) {
            if (emergencyOverride(query)) category = SENSITIVE;

            cout << "Classification: " << LABELS[category] << "\n";
            if (category == SENSITIVE)
                cout << "Safety flag: EMERGENCY\n";
            cout << "Prediction score: 0\n";
            cout << "Top-two margin: 0\n";
            cout << "Matched question: \n";
            cout << "Retrieved answer: \n";
            cout << "Retrieval status: WEAK\n";
            cout << "Assistant: Question forwarded to Flask/Gemini because no embedding words were found.\n\n";
            continue;
        }

        // Classify questions that have at least one known embedding word.
        category = classify(qVec, probs);
        if (emergencyOverride(query)) category = SENSITIVE;

        cout << "Classification: " << LABELS[category] << "\n";
        cout << fixed << setprecision(4)
             << "Class scores: ROUTINE=" << probs[ROUTINE]
             << ", SENSITIVE=" << probs[SENSITIVE]
             << ", UNSUPPORTED=" << probs[UNSUPPORTED] << "\n";

        // 3. Route sensitive or unsupported questions before routine retrieval.
        if (category == SENSITIVE) {
            cout << "Safety flag: " << (emergencyOverride(query) ? "EMERGENCY" : "SENSITIVE") << "\n";
            cout << "Assistant: This question needs human review by clinic staff or a clinician.\n";
            if (emergencyOverride(query))
                cout << "If this is happening now, call 112 in India or go to the nearest emergency department.\n";
            else
                cout << "Please contact reception or request a private staff follow-up.\n";
            cout << "No routine FAQ answer was automatically issued.\n\n";
            continue;
        }

        if (category == UNSUPPORTED) {
            cout << "Assistant: I can only answer questions supported by this clinic's FAQ. "
                    "Please contact reception for this request.\n\n";
            continue;
        }

        // ROUTINE questions are passed to Flask, which supplies FAQ context
        // to Gemini. C++ no longer performs cosine similarity or FAQ matching.
        double topProbability = *max_element(probs.begin(), probs.end());
        cout << "Prediction score: " << topProbability << "\n";
        cout << "Top-two margin: 0\n";
        cout << "Matched question: \n";
        cout << "Retrieved answer: \n";
        cout << "Retrieval status: WEAK\n";
        cout << "Assistant: Routine question forwarded to the generative FAQ backend.\\n\n";
    }

    cout << "Assistant closed.\n";
    return 0;
}
