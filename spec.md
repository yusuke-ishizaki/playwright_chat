英語で思考し、日本語で出力して。
実装にはタスクを作成して、順番に進めていく。
コマンドの実行は確認して。

--- START OF FILE spec.md ---

# playwroght-browser-agent spec.md

## 1. 概要
Streamlitを用いたチャットインターフェースを通じて、ローカルのJSONファイルに定義されたブラウザ操作手順を読み込み、ユーザーの指示に基づいて修正した後、Google Geminiモデルを用いてPlaywrightによるブラウザ自動操作を実行するアプリケーション。
**サーバーサイド（Headless）での実行を前提とし、操作プロセスは動画およびスクリーンショットとして記録・可視化する。**

## 2. 技術スタック & 前提条件
- **Language**: Python 3.10+
- **UI Framework**: `streamlit`
- **LLM Orchestration**: `langchain`, `langchain-google-genai`, `langchain-core`
- **Browser Automation**: `playwright`
    - **重要**: 本プロジェクトでは `langchain-community` の `PlaywrightToolkit` または相当するツール定義を使用する。
    - **可視化ライブラリ**: 動画・画像処理のために標準ライブラリを使用。
- **Data Validation**: `pydantic`
- **LLM Model**: `gemini-2.0-flash-lite-preview` (または利用可能な最新モデルを指定)
- **Environment Variables**: `.env` ファイルで `GOOGLE_API_KEY` を管理

## 3. ディレクトリ構成
```text
.
├── main.py          # Streamlitアプリケーションのエントリーポイント
├── files/           # 操作定義JSONファイルの格納場所
│   └── operations.json
├── media/           # [新規] 実行時に生成されるスクリーンショット・動画の保存先
│   ├── screenshots/
│   └── videos/
├── agents/          # LangChainのエージェント定義
│   └── browser_agent.py
├── models/          # Pydanticモデル定義
│   └── scenario.py
└── .env
```

## 4. データ構造 (Pydantic Models)

### `BrowserScenario` (files/*.json のスキーマ)
```python
class BrowserAction(BaseModel):
    action_type: str = Field(..., description="操作タイプ (例: goto, click, fill, screenshot)")
    selector: Optional[str] = Field(None, description="操作対象のセレクタ")
    value: Optional[str] = Field(None, description="入力値など")
    description: str = Field(..., description="このステップの説明")

class BrowserScenario(BaseModel):
    title: str
    steps: List[BrowserAction]
```

## 5. アプリケーションの状態管理 (st.session_state)
Streamlitの再描画に対応するため、以下のキーを管理する。
- `messages`: チャット履歴 (List[BaseMessage])
- `selected_file`: 現在選択されているJSONファイル名
- `current_scenario`: 読み込まれた(あるいは修正された) `BrowserScenario` オブジェクト
- `agent_state`: エージェントの状態 ("planning", "ready_to_execute", "executing", "finished")
- `execution_results`: 実行結果のメディアファイルパスなどを保持する辞書

## 6. 詳細処理フロー

### Phase 1: 初期化とファイル読み込み
1. サイドバーに `./files` ディレクトリ内の `.json` ファイル一覧を表示する。
2. ユーザーがファイルを選択したら、ファイルを読み込み `st.session_state.current_scenario` に格納する。
3. 読み込んだシナリオの概要（タイトルとステップ一覧）をチャットの初期メッセージとして表示する。
   - システムメッセージ: 「ファイル『{filename}』を読み込みました。以下の手順で操作予定です。(手順を表示)。変更点はありますか？」

### Phase 2: プランニングと修正 (Chat Loop)
1. ユーザーがチャット入力欄で指示を出す（例：「検索ワードを『Python』から『Streamlit』に変えて」）。
2. **Scenario Editor LLM** (Gemini) がユーザーの指示と現在のJSONを受け取り、修正後のJSONデータを生成する。
   - LangChainの `StructuredOutput` または Pydantic parser を使用して、確実にJSON形式で出力させること。
3. 修正された内容で `st.session_state.current_scenario` を更新し、更新後のプランをユーザーに提示する。
4. ユーザーに「実行して良いですか？」と確認を促すUI（ボタンなど）を表示する。

### Phase 3: ブラウザ操作実行 (Agent Execution)
1. ユーザーが同意を示した場合、状態を `executing` に移行する。
2. **Browser Context のセットアップ (重要)**:
   - Playwrightの `browser.new_context` を作成する際、以下の設定を行う：
     - `record_video_dir="./media/videos/"`: 操作全体の録画設定。
     - `record_video_size={"width": 1280, "height": 720}`: 動画サイズの指定。
     - `viewport={"width": 1280, "height": 720}`: ビューポート設定。
   - ブラウザ自体は `headless=True` で起動する。
3. **Agentの実行**:
   - エージェントにシナリオを渡し、ステップごとに実行させる。
   - **スクリーンショットの強制**: 重要なアクション（ページ遷移、フォーム送信後など）の直後に、プログラム的に `page.screenshot(path="...")` を実行し、`./media/screenshots/` にタイムスタンプ付きで保存するロジックを組み込む。
   - 実行経過を `st.status` や `st.expander` でリアルタイム表示する。
4. **終了処理と表示**:
   - **Contextのクローズ**: `context.close()` を呼び出し、動画ファイルをディスクに確実に書き込ませる。
   - **結果表示**:
     - 保存されたスクリーンショットをカルーセルまたは一覧で表示する (`st.image`)。
     - 保存された動画ファイル（`.webm`など）をロードし、プレーヤーを表示する (`st.video`)。
   - 完了メッセージを表示する。

## 7. プロンプト設計要件

### Scenario Modifier Prompt (Phase 2用)
```text
あなたはブラウザ操作シナリオ（JSON）を編集するアシスタントです。
現在のJSON: {current_json}
ユーザーの変更指示: {user_input}

ユーザーの指示に従い、JSONを修正して出力してください。
JSONの構造（スキーマ）は変更しないでください。値のみを変更してください。
```

### Browser Agent Prompt (Phase 3用)
```text
あなたはPlaywrightを使ってブラウザ操作を行うエージェントです。
以下のシナリオ手順に従って正確に操作してください。
シナリオ: {final_scenario_json}

操作は headless モードで行われます。
各ステップの完了を確認し、視覚的な確認が必要なタイミングでは screenshot ツールを使用して画像を保存してください。
エラーが発生した場合は再試行またはユーザーへの報告を行ってください。
```

## 8. 制約事項・エラーハンドリング
- **ブラウザ起動モード**:
    - AWSやRender等のクラウド環境での動作を保証するため、**常に `headless=True` で実行する**。
    - 動作確認手段として `headless=False` は使用せず、**録画データとスクリーンショット**を用いる。
- **非同期処理**:
    - Streamlit内でPlaywrightのasync APIを動作させるため、`asyncio` イベントループの管理に注意する（`nest_asyncio.apply()` の使用を推奨）。
- **メディアファイル管理**:
    - 実行ごとに `media/` フォルダ内の古いファイルをクリーンアップするか、ユニークなIDを付与してファイル名が衝突しないように実装する。