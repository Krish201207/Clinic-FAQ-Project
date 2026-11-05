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


const string EMBEDDING_FILE = "Embeddings.vec";
const string WEIGHTS_FILE = "classifier_weights.txt";
const string FAQ_FILE = "FQA.txt";

const int ROUTINE = 0;
const int SENSITIVE = 1;
const int UNSUPPORTED = 2;
const int CLASS_COUNT = 3;
const string LABELS[CLASS_COUNT] = {"ROUTINE", "SENSITIVE", "UNSUPPORTED"};

const double FAQ_MIN_SIMILARITY = 0.05;
const double FAQ_MIN_MARGIN = 0.025;

struct FAQ {
    string question;
    string answer;
    vector<double> vec;
};

unordered_map<string, vector<double>> wordVectors;
int embeddingVocab = 0;
int DIM = 0;

vector<vector<double>> W;
vector<double> bias;

string lowerCopy(string s) {
    for (char &c : s) {
        c = tolower(c);
    }
    return s;
}

string normalize(string s) {
    for (char &c : s) {
        if (!isalnum(c) && c != '\'')
            c = ' ';
        else
            c = tolower(c);
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
    return true;
}

bool loadFaqs(vector<FAQ> &faqs) {
    ifstream in(FAQ_FILE);
    if (!in) {
        cerr << "ERROR: Cannot open " << FAQ_FILE << ".\n";
        return false;
    }


    vector<string> lines;
    string line;
    while (getline(in, line)) {
        if (line.find_first_not_of(" \t\r") != string::npos)
            lines.push_back(line);
    }

    if (lines.empty() || lines.size() % 2 != 0) {
        cerr << "ERROR: FQA.txt must contain alternating non-empty question/answer lines.\n";
        return false;
    }

    for (size_t i = 0; i < lines.size(); i += 2)
        faqs.push_back({lines[i], lines[i + 1], {}});
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
    getline(in, line); 

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

double cosine(const vector<double> &a, const vector<double> &b) {
    if (a.size() != b.size() || a.empty()) return 0.0;
    double dot = 0.0, na = 0.0, nb = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    if (na < 1e-15 || nb < 1e-15) return 0.0;
    return dot / (sqrt(na) * sqrt(nb));
}




int main(int argc, char *argv[]) {
    const bool machineMode = argc > 1 && string(argv[1]) == "--machine";

    if (!loadEmbeddingHeader() || !loadClassifier()) return 1;

    vector<FAQ> faqs;
    if (!loadFaqs(faqs)) return 1;

    unordered_set<string> faqWords;
    for (const FAQ &faq : faqs)
        for (const string &w : tokenize(faq.question)) faqWords.insert(w);
    loadRequestedWords(faqWords);

    for (FAQ &faq : faqs) {
        int known = 0, total = 0;
        faq.vec = makeSentenceVector(faq.question, known, total);
    }

    string query;
    while (true) {
        if (!machineMode) cout << "Question: ";
        if (!getline(cin, query)) break;

        string command = lowerCopy(query);
        if (command == "exit" || command == "quit") break;

        if (tokenize(query).empty()) {
            if (machineMode) {
                cout << "Classification: UNSUPPORTED\n";
                cout << "Assistant: Please enter a question.\n";
            } else {
                cout << "Category: UNSUPPORTED\n";
                cout << "Answer: Please enter a question.\n\n";
            }
            continue;
        }

        unordered_set<string> queryWords;
        for (const string &w : tokenize(query)) queryWords.insert(w);
        loadRequestedWords(queryWords);

        int known = 0, total = 0;
        vector<double> qVec = makeSentenceVector(query, known, total);

        if (known == 0) {
            if (machineMode) {
                cout << "Classification: UNSUPPORTED\n";
                cout << "Assistant: I could not understand the question. Please rephrase it or contact clinic staff.\n";
            } else {
                cout << "Category: UNSUPPORTED\n";
                cout << "Answer: I could not understand the question. Please rephrase it or contact clinic staff.\n\n";
            }
            continue;
        }

        vector<double> probs;
        int category = classify(qVec, probs);

        if (!machineMode) cout << "Category: " << LABELS[category] << "\n";
        else {
            cout << "Classification: " << LABELS[category] << "\n";
            cout << fixed << setprecision(4)
                 << "Prediction score: " << probs[category] << "\n";
        }

        if (category == SENSITIVE) {
            if (machineMode) {
                cout << "Safety flag: SENSITIVE\n";
                cout << "Assistant: This question needs human review. Please contact clinic staff.\n";
            } else {
                cout << "Answer: This question needs human review. Please contact clinic staff.\n\n";
            }
            continue;
        }

        if (category == UNSUPPORTED) {
            if (machineMode) {
                cout << "Assistant: This question is outside the supported FAQ. Please contact reception.\n";
            } else {
                cout << "Answer: This question is outside the supported FAQ. Please contact reception.\n\n";
            }
            continue;
        }

        int bestIndex = -1;
        double bestScore = -2.0, secondScore = -2.0;

        for (size_t i = 0; i < faqs.size(); ++i) {
            double score = cosine(qVec, faqs[i].vec);
            if (score > bestScore) {
                secondScore = bestScore;
                bestScore = score;
                bestIndex = static_cast<int>(i);
            } else if (score > secondScore) {
                secondScore = score;
            }
        }

        if (secondScore < -1.0) secondScore = -1.0;
        double margin = bestScore - secondScore;
        bool strongMatch = bestIndex >= 0 &&
                           bestScore >= FAQ_MIN_SIMILARITY &&
                           margin >= FAQ_MIN_MARGIN;

        if (machineMode) {
            cout << fixed << setprecision(4)
                 << "Top similarity: " << bestScore << "\n"
                 << "Top-two margin: " << margin << "\n";
            if (bestIndex >= 0) {
                cout << "Matched question: " << faqs[bestIndex].question << "\n";
                cout << "Retrieved answer: " << faqs[bestIndex].answer << "\n";
            } else {
                cout << "Matched question: \n";
                cout << "Retrieved answer: \n";
            }
            cout << "Retrieval status: " << (strongMatch ? "STRONG" : "WEAK") << "\n";
            if (strongMatch) cout << "Assistant: " << faqs[bestIndex].answer << "\n";
            else cout << "Assistant: No confident FAQ match found. Please contact clinic staff.\n";
        } else {
            if (strongMatch) {
                cout << "Answer: " << faqs[bestIndex].answer << "\n\n";
            } else {
                cout << "Answer: No confident FAQ match found. Please contact clinic staff.\n\n";
            }
        }
    }

    return 0;
}
