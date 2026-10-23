package br.com.controlepc;

import android.app.Activity;
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

    private static final String ENDERECO_PADRAO = "http://192.168.0.100:5000";

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
