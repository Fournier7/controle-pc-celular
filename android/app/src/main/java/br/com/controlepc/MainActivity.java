package br.com.controlepc;

import android.app.Activity;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.net.Uri;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;

public class MainActivity extends Activity {

    private static final String ENDERECO_PADRAO = "http://IP-DO-PC:5000";

    private ValueCallback<Uri[]> retornoArquivos;
    private static final int ESCOLHER_ARQUIVOS = 1001;
    private WebView web;
    private SharedPreferences prefs;
    private boolean dialogoAberto = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("config", MODE_PRIVATE);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0A0A0B"));
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // guarda o token entre aberturas
        s.setTextZoom(100);

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> retorno,
                                             FileChooserParams parametros) {
                if (retornoArquivos != null) retornoArquivos.onReceiveValue(null);
                retornoArquivos = retorno;
                Intent escolher = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                escolher.addCategory(Intent.CATEGORY_OPENABLE);
                escolher.setType("*/*");
                escolher.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(escolher, ESCOLHER_ARQUIVOS);
                } catch (ActivityNotFoundException erro) {
                    retornoArquivos.onReceiveValue(null);
                    retornoArquivos = null;
                    new AlertDialog.Builder(MainActivity.this)
                            .setMessage("Não foi possível abrir o seletor de arquivos.")
                            .setPositiveButton("OK", null).show();
                }
                return true;
            }
        });

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) {
                    v.loadUrl("about:blank");
                    falhou();
                }
            }
        });

        if (prefs.getString("url", null) == null) {
            pedirEndereco();
        } else {
            carregar();
        }
    }

    @Override
    protected void onActivityResult(int pedido, int resultado, Intent dados) {
        super.onActivityResult(pedido, resultado, dados);
        if (pedido != ESCOLHER_ARQUIVOS || retornoArquivos == null) return;
        Uri[] arquivos = null;
        if (resultado == RESULT_OK && dados != null) {
            if (dados.getClipData() != null) {
                int quantidade = dados.getClipData().getItemCount();
                arquivos = new Uri[quantidade];
                for (int i = 0; i < quantidade; i++) {
                    arquivos[i] = dados.getClipData().getItemAt(i).getUri();
                }
            } else if (dados.getData() != null) {
                arquivos = new Uri[]{dados.getData()};
            }
        }
        retornoArquivos.onReceiveValue(arquivos);
        retornoArquivos = null;
    }

    @Override
    protected void onDestroy() {
        if (retornoArquivos != null) {
            retornoArquivos.onReceiveValue(null);
            retornoArquivos = null;
        }
        super.onDestroy();
    }

    private void carregar() {
        web.loadUrl(prefs.getString("url", ENDERECO_PADRAO));
    }

    private void pedirEndereco() {
        final EditText campo = new EditText(this);
        campo.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        campo.setSingleLine(true);
        campo.setText(prefs.getString("url", ENDERECO_PADRAO));

        new AlertDialog.Builder(this)
                .setTitle("Endereço do PC")
                .setMessage("Digite o endereço que aparece na janela do servidor.")
                .setView(campo)
                .setCancelable(false)
                .setPositiveButton("Salvar", (d, w) -> {
                    String t = campo.getText().toString().trim();
                    if (!t.startsWith("http")) t = "http://" + t;
                    prefs.edit().putString("url", t).apply();
                    carregar();
                })
                .show();
    }

    private void falhou() {
        if (dialogoAberto) return;
        dialogoAberto = true;
        new AlertDialog.Builder(this)
                .setTitle("Não consegui conectar")
                .setMessage("Confira se o PC está ligado, se o servidor está aberto e se o celular está no mesmo Wi-Fi.")
                .setCancelable(false)
                .setPositiveButton("Tentar de novo", (d, w) -> {
                    dialogoAberto = false;
                    carregar();
                })
                .setNegativeButton("Mudar endereço", (d, w) -> {
                    dialogoAberto = false;
                    pedirEndereco();
                })
                .show();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
